using System.Text;
using System.Text.Json.Serialization;
using LLama;
using LLama.Common;
using LLama.Sampling;

var builder = WebApplication.CreateBuilder(args);
builder.WebHost.UseUrls(args.Length > 0 ? args[0] : "http://127.0.0.1:18080");

var app = builder.Build();
var modelState = new ModelState();

app.MapGet("/health", () => Results.Ok(new HealthResponse(true, modelState.IsLoaded)));

app.MapPost("/v1/model/load", async (LoadModelRequest request) =>
{
    if (string.IsNullOrWhiteSpace(request.ModelPath))
    {
        return Results.BadRequest(new ErrorResponse("model_path is required."));
    }

    if (!request.ModelPath.EndsWith(".gguf", StringComparison.OrdinalIgnoreCase))
    {
        return Results.BadRequest(new ErrorResponse("Only .gguf models are supported."));
    }

    if (!File.Exists(request.ModelPath))
    {
        return Results.BadRequest(new ErrorResponse("Model file does not exist."));
    }

    try
    {
        await Task.Run(() => modelState.Load(request));
        return Results.Ok(new LoadModelResponse(true, Path.GetFileName(request.ModelPath)));
    }
    catch (Exception ex)
    {
        modelState.Unload();
        return Results.Json(new ErrorResponse($"Failed to load model: {ex.Message}"), statusCode: 500);
    }
});

app.MapPost("/v1/model/unload", () =>
{
    modelState.Unload();
    return Results.Ok(new UnloadModelResponse(true));
});

app.MapPost("/v1/chat/completions", async (ChatCompletionRequest request) =>
{
    if (!modelState.IsLoaded)
    {
        return Results.BadRequest(new ErrorResponse("Model is not loaded."));
    }

    var prompt = request.ToPrompt();
    if (string.IsNullOrWhiteSpace(prompt))
    {
        return Results.BadRequest(new ErrorResponse("messages are required."));
    }

    try
    {
        var content = await modelState.GenerateAsync(prompt, request.MaxTokens ?? 512, request.Temperature ?? 0.1f);
        return Results.Ok(ChatCompletionResponse.FromContent(request.Model ?? "local-gguf", content));
    }
    catch (Exception ex)
    {
        return Results.Json(new ErrorResponse($"Failed to generate response: {ex.Message}"), statusCode: 500);
    }
});

app.Lifetime.ApplicationStopping.Register(modelState.Unload);
app.Run();

internal sealed class ModelState : IDisposable
{
    private readonly object sync = new();
    private LLamaWeights? weights;
    private LLamaContext? context;
    private InteractiveExecutor? executor;

    public bool IsLoaded
    {
        get
        {
            lock (sync)
            {
                return executor is not null;
            }
        }
    }

    public void Load(LoadModelRequest request)
    {
        lock (sync)
        {
            Unload();
            var parameters = new ModelParams(request.ModelPath)
            {
                ContextSize = request.ContextSize ?? 2048,
                GpuLayerCount = request.GpuLayers ?? 0,
            };

            weights = LLamaWeights.LoadFromFile(parameters);
            context = weights.CreateContext(parameters);
            executor = new InteractiveExecutor(context);
        }
    }

    public async Task<string> GenerateAsync(string prompt, int maxTokens, float temperature)
    {
        InteractiveExecutor currentExecutor;
        lock (sync)
        {
            currentExecutor = executor ?? throw new InvalidOperationException("Model is not loaded.");
        }

        var inferenceParams = new InferenceParams
        {
            MaxTokens = maxTokens,
            AntiPrompts = ["</s>"],
            SamplingPipeline = new DefaultSamplingPipeline
            {
                Temperature = temperature,
            },
        };

        var builder = new StringBuilder();
        await foreach (var token in currentExecutor.InferAsync(prompt, inferenceParams))
        {
            builder.Append(token);
        }
        return builder.ToString();
    }

    public void Unload()
    {
        lock (sync)
        {
            executor = null;
            context?.Dispose();
            weights?.Dispose();
            context = null;
            weights = null;
        }
    }

    public void Dispose() => Unload();
}

internal sealed record LoadModelRequest(
    [property: JsonPropertyName("model_path")] string ModelPath,
    [property: JsonPropertyName("context_size")] uint? ContextSize,
    [property: JsonPropertyName("gpu_layers")] int? GpuLayers);

internal sealed record LoadModelResponse(bool Ok, string Model);

internal sealed record UnloadModelResponse(bool Ok);

internal sealed record HealthResponse(bool Ok, bool ModelLoaded);

internal sealed record ErrorResponse(string Error);

internal sealed record ChatCompletionRequest(
    string? Model,
    ChatMessage[]? Messages,
    [property: JsonPropertyName("max_tokens")] int? MaxTokens,
    float? Temperature)
{
    public string ToPrompt()
    {
        if (Messages is null || Messages.Length == 0)
        {
            return string.Empty;
        }

        var builder = new StringBuilder();
        foreach (var message in Messages)
        {
            builder.AppendLine($"{message.Role}: {message.Content}");
        }
        builder.Append("assistant: ");
        return builder.ToString();
    }
}

internal sealed record ChatMessage(string Role, string Content);

internal sealed record ChatCompletionResponse(
    string Id,
    string Object,
    long Created,
    string Model,
    ChatChoice[] Choices)
{
    public static ChatCompletionResponse FromContent(string model, string content)
    {
        return new ChatCompletionResponse(
            $"chatcmpl-{Guid.NewGuid():N}",
            "chat.completion",
            DateTimeOffset.UtcNow.ToUnixTimeSeconds(),
            model,
            [new ChatChoice(0, new ChatMessage("assistant", content), "stop")]);
    }
}

internal sealed record ChatChoice(int Index, ChatMessage Message, [property: JsonPropertyName("finish_reason")] string FinishReason);

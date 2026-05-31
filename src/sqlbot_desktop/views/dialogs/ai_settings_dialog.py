"""AI settings dialog for Local GGUF and API backends."""

from __future__ import annotations

import ctypes
import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from sqlbot_desktop.models.entities import AIBackend, AIModelConfig


class AISettingsDialog(QDialog):
    """Configure the active AI backend without loading it automatically."""

    def __init__(self, config: AIModelConfig, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AI Settings")
        self.setMinimumSize(760, 520)

        self.backend_combo = QComboBox()
        self.model_combo = QComboBox()
        self.model_path_input = QLineEdit()
        self.api_endpoint_input = QLineEdit()
        self.api_model_input = QLineEdit()
        self.context_size_spin = QSpinBox()
        self.max_tokens_spin = QSpinBox()
        self.threads_spin = QSpinBox()
        self.model_info = QLabel("")
        self.resource_info = QLabel("")
        self.test_output = QTextEdit()
        self.local_panel = QFrame()
        self.api_panel = QFrame()

        self._build_ui()
        self._load_models()
        self.set_config(config)
        self._sync_mode()

    def config(self) -> AIModelConfig:
        backend = AIBackend(self.backend_combo.currentData())
        return AIModelConfig(
            backend=backend,
            local_model_path=self.model_path_input.text().strip(),
            api_endpoint=self.api_endpoint_input.text().strip(),
            api_model=self.api_model_input.text().strip(),
            context_size=self.context_size_spin.value(),
            max_tokens=self.max_tokens_spin.value(),
            threads=self.threads_spin.value(),
        )

    def set_config(self, config: AIModelConfig) -> None:
        backend_index = self.backend_combo.findData(config.backend.value)
        self.backend_combo.setCurrentIndex(max(backend_index, 0))
        self.model_path_input.setText(config.local_model_path)
        self.api_endpoint_input.setText(config.api_endpoint)
        self.api_model_input.setText(config.api_model)
        self.context_size_spin.setValue(config.context_size or 4096)
        self.max_tokens_spin.setValue(config.max_tokens or 512)
        self.threads_spin.setValue(config.threads or 4)
        self._select_model_path(config.local_model_path)
        self._refresh_model_info()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        title = QLabel("AI Settings")
        title.setObjectName("dialogTitle")
        caption = QLabel("Chọn Local GGUF hoặc API AI. Chỉ nhóm cấu hình đang chọn được hiển thị.")
        caption.setObjectName("dialogCaption")
        caption.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(caption)

        mode_row = QHBoxLayout()
        self.backend_combo.addItem("Local GGUF", AIBackend.LOCAL.value)
        self.backend_combo.addItem("API AI", AIBackend.API.value)
        self.backend_combo.currentIndexChanged.connect(self._sync_mode)
        mode_row.addWidget(QLabel("Backend"))
        mode_row.addWidget(self.backend_combo, 1)
        layout.addLayout(mode_row)

        self._build_local_panel()
        self._build_api_panel()
        layout.addWidget(self.local_panel)
        layout.addWidget(self.api_panel)

        # Token Manager Section
        token_panel = QFrame()
        token_panel.setObjectName("settingsPanel")
        token_layout = QHBoxLayout(token_panel)
        token_layout.setSpacing(14)

        self.context_size_spin.setRange(256, 32768)
        self.context_size_spin.setSingleStep(256)
        self.context_size_spin.setValue(4096)
        self.context_size_spin.setAccessibleName("Context size limit")

        self.max_tokens_spin.setRange(64, 8192)
        self.max_tokens_spin.setSingleStep(64)
        self.max_tokens_spin.setValue(512)
        self.max_tokens_spin.setAccessibleName("Max output tokens")

        self.threads_spin.setRange(1, 32)
        self.threads_spin.setSingleStep(1)
        self.threads_spin.setValue(4)
        self.threads_spin.setAccessibleName("CPU threads count")

        token_layout.addWidget(QLabel("Context Size (n_ctx)"))
        token_layout.addWidget(self.context_size_spin, 1)
        token_layout.addWidget(QLabel("Max Tokens (max_tokens)"))
        token_layout.addWidget(self.max_tokens_spin, 1)
        token_layout.addWidget(QLabel("Threads (luồng)"))
        token_layout.addWidget(self.threads_spin, 1)

        layout.addWidget(token_panel)

        self.test_output.setReadOnly(True)
        self.test_output.setFixedHeight(86)
        self.test_output.setPlaceholderText("Test result")
        layout.addWidget(self.test_output)

        actions = QHBoxLayout()
        test_button = QPushButton("Test Inference")
        test_button.setObjectName("secondaryButton")
        save_button = QPushButton("Save")
        save_button.setObjectName("primaryButton")
        cancel_button = QPushButton("Cancel")
        cancel_button.setObjectName("secondaryButton")
        test_button.clicked.connect(self._test_settings)
        save_button.clicked.connect(self._accept_if_valid)
        cancel_button.clicked.connect(self.reject)
        actions.addWidget(test_button)
        actions.addStretch()
        actions.addWidget(cancel_button)
        actions.addWidget(save_button)
        layout.addLayout(actions)

    def _build_local_panel(self) -> None:
        self.local_panel.setObjectName("settingsPanel")
        layout = QVBoxLayout(self.local_panel)
        layout.setSpacing(10)

        row = QHBoxLayout()
        self.model_combo.currentIndexChanged.connect(self._model_selected)
        refresh_button = QPushButton("Scan")
        refresh_button.setObjectName("secondaryButton")
        browse_button = QPushButton("Browse GGUF")
        browse_button.setObjectName("secondaryButton")
        refresh_button.clicked.connect(self._load_models)
        browse_button.clicked.connect(self._browse_model)
        row.addWidget(QLabel("Model"))
        row.addWidget(self.model_combo, 1)
        row.addWidget(refresh_button)
        row.addWidget(browse_button)
        layout.addLayout(row)

        self.model_path_input.setPlaceholderText("Đường dẫn file .gguf")
        self.model_path_input.textChanged.connect(lambda _: self._refresh_model_info())
        layout.addWidget(self.model_path_input)

        self.model_info.setObjectName("statusLabel")
        self.model_info.setWordWrap(True)
        self.resource_info.setObjectName("formHint")
        self.resource_info.setWordWrap(True)
        layout.addWidget(self.model_info)
        layout.addWidget(self.resource_info)

    def _build_api_panel(self) -> None:
        self.api_panel.setObjectName("settingsPanel")
        layout = QVBoxLayout(self.api_panel)
        layout.setSpacing(10)

        self.api_endpoint_input.setPlaceholderText("https://api.openai.com/v1/chat/completions")
        self.api_model_input.setPlaceholderText("API model, ví dụ gpt-4.1-mini")
        layout.addWidget(QLabel("API endpoint"))
        layout.addWidget(self.api_endpoint_input)
        layout.addWidget(QLabel("API model"))
        layout.addWidget(self.api_model_input)

        hint = QLabel("API key đọc từ biến môi trường SQLBOT_AI_API_KEY.")
        hint.setObjectName("formHint")
        layout.addWidget(hint)

    def _load_models(self) -> None:
        current_path = self.model_path_input.text().strip()
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        for model_path in self._model_files():
            self.model_combo.addItem(model_path.name, str(model_path))
        self.model_combo.blockSignals(False)
        self._select_model_path(current_path)
        if not self.model_path_input.text().strip() and self.model_combo.count() > 0:
            self.model_combo.setCurrentIndex(0)
            self._model_selected()
        self._refresh_model_info()

    def _model_files(self) -> list[Path]:
        roots = [Path("models"), Path("AI Models")]
        files: list[Path] = []
        for root in roots:
            if root.exists():
                files.extend(path for path in root.rglob("*.gguf") if path.is_file())
        return sorted(files, key=lambda path: path.name.lower())

    def _select_model_path(self, model_path: str) -> None:
        if not model_path:
            return
        index = self.model_combo.findData(model_path)
        if index >= 0:
            self.model_combo.setCurrentIndex(index)

    def _model_selected(self) -> None:
        path = self.model_combo.currentData()
        if path:
            self.model_path_input.setText(str(path))

    def _browse_model(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Chọn GGUF model", "", "GGUF models (*.gguf)")
        if file_path:
            self.model_path_input.setText(file_path)
            self._select_model_path(file_path)

    def _refresh_model_info(self) -> None:
        model_path = Path(self.model_path_input.text().strip())
        if not model_path.exists():
            self.model_info.setText("Chưa chọn model GGUF hợp lệ.")
            self.resource_info.setText(self._resource_summary())
            return

        size_gb = model_path.stat().st_size / (1024**3)
        quantization = self._guess_quantization(model_path.name)
        self.model_info.setText(f"{model_path.name} | {size_gb:.2f} GB | quantization: {quantization}")
        self.resource_info.setText(self._resource_summary(size_gb))

    def _guess_quantization(self, name: str) -> str:
        parts = Path(name).stem.split("-")
        for part in reversed(parts):
            upper = part.upper()
            if upper.startswith("Q") or upper in {"F16", "BF16", "F32"}:
                return part
        return "unknown"

    def _resource_summary(self, model_size_gb: float | None = None) -> str:
        cpu = os.cpu_count() or 1
        ram_gb = self._total_ram_gb()
        parts = [f"CPU cores: {cpu}"]
        if ram_gb:
            parts.append(f"RAM: {ram_gb:.1f} GB")
        if model_size_gb is not None and ram_gb:
            needed = model_size_gb * 1.4
            status = "OK" if ram_gb >= needed else "RAM có thể không đủ"
            parts.append(f"estimated need: {needed:.1f} GB ({status})")
        return " | ".join(parts)

    def _total_ram_gb(self) -> float | None:
        if os.name != "nt":
            return None

        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(MemoryStatus)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
        return status.ullTotalPhys / (1024**3)

    def _sync_mode(self) -> None:
        is_local = self.backend_combo.currentData() == AIBackend.LOCAL.value
        self.local_panel.setVisible(is_local)
        self.api_panel.setVisible(not is_local)

    def _test_settings(self) -> None:
        config = self.config()
        if config.backend == AIBackend.LOCAL:
            path = Path(config.local_model_path)
            if path.suffix.lower() != ".gguf" or not path.exists():
                self.test_output.setPlainText("Local GGUF chưa hợp lệ.")
                return
            self.test_output.setPlainText(
                "Local GGUF hợp lệ. Bấm Load ở Main Window để load model, sau đó dùng Generate SQL để test inference."
            )
            return

        if not config.api_endpoint.strip() or not config.api_model.strip():
            self.test_output.setPlainText("API endpoint và API model là bắt buộc.")
            return
        self.test_output.setPlainText("API settings hợp lệ. API key sẽ được đọc từ SQLBOT_AI_API_KEY.")

    def _accept_if_valid(self) -> None:
        config = self.config()
        if config.backend == AIBackend.LOCAL:
            path = Path(config.local_model_path)
            if path.suffix.lower() != ".gguf" or not path.exists():
                QMessageBox.warning(self, "Model không hợp lệ", "Vui lòng chọn file .gguf tồn tại.")
                return
        elif not config.api_endpoint.strip() or not config.api_model.strip():
            QMessageBox.warning(self, "API chưa đủ", "Vui lòng nhập API endpoint và API model.")
            return
        self.accept()

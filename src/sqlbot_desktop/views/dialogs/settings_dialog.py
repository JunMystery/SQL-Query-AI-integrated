"""Integrated Settings Dialog containing AI Settings and Schema Annotations with page-level actions."""

from __future__ import annotations

import ctypes
import os
import json
from pathlib import Path
from sqlbot_desktop.utils.i18n_manager import tr

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QListWidget,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
)

from sqlbot_desktop.models.entities import AIBackend, AIModelConfig, TableInfo
from sqlbot_desktop.infrastructure.annotation_repository import AnnotationRepository

ROLE_KIND = Qt.ItemDataRole.UserRole
ROLE_TABLE = Qt.ItemDataRole.UserRole + 1
ROLE_COLUMN = Qt.ItemDataRole.UserRole + 2


class AISettingsWidget(QWidget):
    """Widget to configure the active AI backend."""

    load_model_requested = Signal(AIModelConfig)
    unload_model_requested = Signal()
    save_requested = Signal()

    def __init__(self, config: AIModelConfig, parent=None) -> None:
        super().__init__(parent)

        self.backend_combo = QComboBox()
        self.model_combo = QComboBox()
        self.model_path_input = QLineEdit()
        self.api_endpoint_input = QLineEdit()
        self.api_model_input = QLineEdit()
        self.api_key_input = QLineEdit()
        self.context_size_spin = QSpinBox()
        self.max_tokens_spin = QSpinBox()
        self.threads_spin = QSpinBox()
        self.cpu_limit_spin = QSpinBox()
        self.self_correction_spin = QSpinBox()
        self.gpu_layers_spin = QSpinBox()
        self.threads_label = QLabel("Luồng suy luận LLM")
        self.threads_hint = QLabel(
            "Thiết lập này là số worker thread llama.cpp dùng khi suy luận GGUF, "
            "không phải giới hạn % CPU hoặc khóa đúng từng core CPU. "
            "Giảm xuống 1-2 nếu model local làm CPU quá cao."
        )
        self.model_info = QLabel("")
        self.resource_info = QLabel("")
        self.test_output = QTextEdit()
        self.local_panel = QFrame()
        self.api_panel = QFrame()
        self._model_scan_cache: list[Path] = []

        self._build_ui()
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
            gpu_layers=self.gpu_layers_spin.value(),
            cpu_thread_limit=self.cpu_limit_spin.value(),
            self_correction_retries=self.self_correction_spin.value(),
            api_key=self.api_key_input.text().strip(),
        )

    def set_config(self, config: AIModelConfig) -> None:
        backend_index = self.backend_combo.findData(config.backend.value)
        self.backend_combo.setCurrentIndex(max(backend_index, 0))
        self.model_path_input.setText(config.local_model_path)
        self.api_endpoint_input.setText(config.api_endpoint)
        self.api_model_input.setText(config.api_model)
        self.api_key_input.setText(getattr(config, "api_key", ""))
        self.context_size_spin.setValue(config.context_size or 2048)
        self.max_tokens_spin.setValue(config.max_tokens or 512)
        self.threads_spin.setValue(config.threads or 2)
        self.gpu_layers_spin.setValue(getattr(config, "gpu_layers", 0))
        self.cpu_limit_spin.setValue(getattr(config, "cpu_thread_limit", 4))
        self.self_correction_spin.setValue(getattr(config, "self_correction_retries", 3))
        self._select_model_path(config.local_model_path)
        self._refresh_model_info()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        self.title_label = QLabel()
        self.title_label.setObjectName("dialogTitle")
        self.caption_label = QLabel()
        self.caption_label.setObjectName("dialogCaption")
        self.caption_label.setWordWrap(True)
        layout.addWidget(self.title_label)
        layout.addWidget(self.caption_label)

        mode_row = QHBoxLayout()
        self.backend_combo.addItem("Local GGUF", AIBackend.LOCAL.value)
        self.backend_combo.addItem("API AI", AIBackend.API.value)
        self.backend_combo.currentIndexChanged.connect(self._sync_mode)
        self.backend_label = QLabel()
        mode_row.addWidget(self.backend_label)
        mode_row.addWidget(self.backend_combo, 1)
        layout.addLayout(mode_row)

        self._build_local_panel()
        self._build_api_panel()
        layout.addWidget(self.local_panel)
        layout.addWidget(self.api_panel)

        # Token Manager Section
        token_panel = QFrame()
        token_panel.setObjectName("settingsPanel")
        token_layout = QGridLayout(token_panel)
        token_layout.setSpacing(14)

        self.context_size_spin.setRange(256, 32768)
        self.context_size_spin.setSingleStep(256)
        self.context_size_spin.setValue(2048)
        self.context_size_spin.setAccessibleName("Context size limit")

        self.max_tokens_spin.setRange(64, 8192)
        self.max_tokens_spin.setSingleStep(64)
        self.max_tokens_spin.setValue(512)
        self.max_tokens_spin.setAccessibleName("Max output tokens")

        self.threads_spin.setRange(1, 32)
        self.threads_spin.setSingleStep(1)
        self.threads_spin.setValue(2)
        self.threads_spin.setAccessibleName("Số luồng suy luận LLM")
        self.threads_spin.setToolTip(
            "Số worker thread llama.cpp dùng khi suy luận GGUF local. "
            "Đây không phải giới hạn phần trăm CPU hoặc số core CPU được giữ riêng."
        )
        self.threads_spin.valueChanged.connect(lambda _: self._refresh_model_info())
        self.threads_label.setToolTip(self.threads_spin.toolTip())

        self.cpu_limit_spin.setRange(0, 64)
        self.cpu_limit_spin.setSingleStep(1)
        self.cpu_limit_spin.setValue(4)
        self.cpu_limit_spin.setAccessibleName("Giới hạn logical CPU cho app")
        self.cpu_limit_spin.setSpecialValueText("Không giới hạn")
        self.cpu_limit_spin.setToolTip(
            "Giới hạn CPU affinity của toàn bộ app. 0 nghĩa là không giới hạn; "
            "4 phù hợp laptop i5 gen 11, RAM 16GB, không VGA rời."
        )
        self.cpu_limit_spin.valueChanged.connect(lambda _: self._refresh_model_info())

        self.self_correction_spin.setRange(1, 5)
        self.self_correction_spin.setSingleStep(1)
        self.self_correction_spin.setValue(3)
        self.self_correction_spin.setAccessibleName("So lan tu sua SQL")
        self.self_correction_spin.setToolTip(
            "So lan toi da AI sinh lai SQL khi SELECT bi loi execution. Mac dinh 3."
        )

        self.gpu_layers_spin.setRange(0, 200)
        self.gpu_layers_spin.setSingleStep(1)
        self.gpu_layers_spin.setValue(0)
        self.gpu_layers_spin.setAccessibleName("GPU offload layers")

        self.ctx_size_label = QLabel("Context Size (n_ctx)")
        self.max_tok_label = QLabel("Max Tokens (max_tokens)")
        self.cpu_limit_label = QLabel("CPU Limit")
        self.self_correct_label = QLabel("Self-Correct")
        self.gpu_layers_label = QLabel("GPU Layers")

        token_layout.addWidget(self.ctx_size_label, 0, 0)
        token_layout.addWidget(self.context_size_spin, 0, 1)
        token_layout.addWidget(self.max_tok_label, 0, 2)
        token_layout.addWidget(self.max_tokens_spin, 0, 3)
        token_layout.addWidget(self.threads_label, 0, 4)
        token_layout.addWidget(self.threads_spin, 0, 5)
        token_layout.addWidget(self.cpu_limit_label, 1, 0)
        token_layout.addWidget(self.cpu_limit_spin, 1, 1)
        token_layout.addWidget(self.self_correct_label, 1, 2)
        token_layout.addWidget(self.self_correction_spin, 1, 3)
        token_layout.addWidget(self.gpu_layers_label, 1, 4)
        token_layout.addWidget(self.gpu_layers_spin, 1, 5)

        layout.addWidget(token_panel)
        self.threads_hint.setObjectName("formHint")
        self.threads_hint.setWordWrap(True)
        layout.addWidget(self.threads_hint)

        self.test_output.setReadOnly(True)
        self.test_output.setFixedHeight(86)
        layout.addWidget(self.test_output)

        actions = QHBoxLayout()
        self.test_button = QPushButton()
        self.test_button.setObjectName("secondaryButton")
        self.load_button = QPushButton()
        self.load_button.setObjectName("successButton")
        self.unload_button = QPushButton()
        self.unload_button.setObjectName("dangerButton")
        self.save_button = QPushButton()
        self.save_button.setObjectName("primaryButton")

        self.test_button.clicked.connect(self._test_settings)
        self.load_button.clicked.connect(self._request_load)
        self.unload_button.clicked.connect(self._request_unload)
        self.save_button.clicked.connect(self._accept_if_valid)

        actions.addWidget(self.test_button)
        actions.addStretch()
        actions.addWidget(self.load_button)
        actions.addWidget(self.unload_button)
        actions.addWidget(self.save_button)
        layout.addLayout(actions)
        
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self.title_label.setText(tr("settings.tab_ai_config", "Cài đặt AI"))
        self.caption_label.setText(tr("settings.ai_caption", "Chọn Local GGUF hoặc API AI. Chỉ nhóm cấu hình đang chọn được hiển thị."))
        self.backend_label.setText(tr("settings.ai_provider", "Nhà cung cấp AI:"))
        
        # update combos if we want to translate items:
        curr_idx = self.backend_combo.currentIndex()
        self.backend_combo.blockSignals(True)
        self.backend_combo.clear()
        self.backend_combo.addItem("Local GGUF", AIBackend.LOCAL.value)
        self.backend_combo.addItem("API AI", AIBackend.API.value)
        self.backend_combo.setCurrentIndex(curr_idx)
        self.backend_combo.blockSignals(False)
        
        self.ctx_size_label.setText(tr("settings.ai_ctx_size", "Context Size (n_ctx)"))
        self.max_tok_label.setText(tr("settings.ai_max_tokens", "Max Tokens (max_tokens)"))
        self.threads_label.setText(tr("settings.ai_threads", "Luồng suy luận LLM"))
        self.cpu_limit_label.setText(tr("settings.ai_cpu_limit", "CPU Limit"))
        self.self_correct_label.setText(tr("settings.ai_self_correct", "Self-Correct"))
        self.gpu_layers_label.setText(tr("settings.ai_gpu_layers", "GPU Layers"))
        
        self.threads_hint.setText(tr("settings.ai_threads_hint", "Thiết lập này là số worker thread llama.cpp dùng khi suy luận GGUF local. Đây không phải giới hạn phần trăm CPU hoặc số core CPU được giữ riêng."))
        self.test_output.setPlaceholderText(tr("settings.ai_test_placeholder", "Kết quả kiểm tra suy luận..."))
        
        self.test_button.setText(tr("settings.ai_btn_test", "Test Inference"))
        self.load_button.setText(tr("settings.ai_btn_load", "Load Model"))
        self.unload_button.setText(tr("settings.ai_btn_unload", "Unload Model"))
        self.save_button.setText(tr("settings.btn_save_config", "Lưu cấu hình"))
        
        self.model_path_input.setPlaceholderText(tr("settings.ai_gguf_path_placeholder", "Đường dẫn file .gguf"))
        self.api_endpoint_input.setPlaceholderText(tr("settings.ai_api_endpoint_placeholder", "https://api.openai.com/v1/chat/completions"))
        self.api_model_input.setPlaceholderText(tr("settings.ai_api_model_placeholder", "API model, ví dụ gpt-4.1-mini"))
        self.api_key_input.setPlaceholderText(tr("settings.ai_api_key_placeholder", "API Key (Có thể bỏ trống)"))

        self.threads_spin.setToolTip(tr("settings.ai_threads_hint", "Thiết lập này là số worker thread llama.cpp dùng khi suy luận GGUF local. Đây không phải giới hạn phần trăm CPU hoặc số core CPU được giữ riêng."))
        self.threads_label.setToolTip(self.threads_spin.toolTip())
        self.cpu_limit_spin.setToolTip(tr("settings.ai_cpu_limit_tooltip", "Giới hạn CPU affinity của toàn bộ app. 0 nghĩa là không giới hạn; 4 phù hợp laptop i5 gen 11, RAM 16GB, không VGA rời."))
        self.cpu_limit_spin.setSpecialValueText(tr("settings.cpu_no_limit", "Không giới hạn"))
        self.self_correction_spin.setToolTip(tr("settings.ai_self_correct_tooltip", "Số lần tối đa AI sinh lại SQL khi SELECT bị lỗi execution. Mặc định 3."))
        
        if hasattr(self, "local_title"):
            self.local_title.setText(tr("settings.ai_local_config", "Cấu hình local model llama.cpp"))
        if hasattr(self, "api_title"):
            self.api_title.setText(tr("settings.ai_api_config", "Cấu hình API bên thứ ba"))
            
        if hasattr(self, "model_lbl"):
            self.model_lbl.setText(tr("settings.ai_model_name"))
        if hasattr(self, "path_lbl"):
            self.path_lbl.setText(tr("settings.ai_gguf_path"))
        if hasattr(self, "scan_btn"):
            self.scan_btn.setText(tr("settings.ai_btn_scan", "Scan"))
        if hasattr(self, "browse_btn"):
            self.browse_btn.setText(tr("settings.btn_browse", "Chọn file..."))
            
        if hasattr(self, "endpoint_lbl"):
            self.endpoint_lbl.setText(tr("settings.ai_base_url"))
        if hasattr(self, "api_model_lbl"):
            self.api_model_lbl.setText(tr("settings.ai_model_name"))
        if hasattr(self, "api_key_lbl"):
            self.api_key_lbl.setText(tr("settings.ai_api_key"))

    def _build_local_panel(self) -> None:
        self.local_panel.setObjectName("settingsPanel")
        layout = QVBoxLayout(self.local_panel)
        layout.setSpacing(10)

        self.local_title = QLabel()
        self.local_title.setStyleSheet("font-weight: bold; color: #1e293b;")
        layout.addWidget(self.local_title)

        row = QHBoxLayout()
        self.model_combo.currentIndexChanged.connect(self._model_selected)
        self.scan_btn = QPushButton("Scan")
        self.scan_btn.setObjectName("secondaryButton")
        self.browse_btn = QPushButton("Browse GGUF")
        self.browse_btn.setObjectName("secondaryButton")
        self.scan_btn.clicked.connect(self._load_models)
        self.browse_btn.clicked.connect(self._browse_model)
        self.model_lbl = QLabel("Model")
        row.addWidget(self.model_lbl)
        row.addWidget(self.model_combo, 1)
        row.addWidget(self.scan_btn)
        row.addWidget(self.browse_btn)
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

        self.api_title = QLabel()
        self.api_title.setStyleSheet("font-weight: bold; color: #1e293b;")
        layout.addWidget(self.api_title)

        self.api_endpoint_input.setPlaceholderText("https://api.openai.com/v1/chat/completions")
        self.api_model_input.setPlaceholderText("API model, ví dụ gpt-4.1-mini")
        self.api_key_input.setPlaceholderText("API Key (Có thể bỏ trống)")
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)

        self.endpoint_lbl = QLabel("API endpoint")
        self.api_model_lbl = QLabel("API model")
        self.api_key_lbl = QLabel("API Key")

        layout.addWidget(self.endpoint_lbl)
        layout.addWidget(self.api_endpoint_input)
        layout.addWidget(self.api_model_lbl)
        layout.addWidget(self.api_model_input)
        layout.addWidget(self.api_key_lbl)
        layout.addWidget(self.api_key_input)

    def _load_models(self) -> None:
        current_path = self.model_path_input.text().strip()
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self._model_scan_cache = self._model_files()
        for model_path in self._model_scan_cache:
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
        max_results = 100
        for root in roots:
            if not root.exists():
                continue
            try:
                candidates = list(root.glob("*.gguf"))
                for child in root.iterdir():
                    if child.is_dir():
                        candidates.extend(child.glob("*.gguf"))
            except OSError:
                continue
            for path in candidates:
                if path.is_file():
                    files.append(path)
                if len(files) >= max_results:
                    return sorted(files, key=lambda item: item.name.lower())
        return sorted(files, key=lambda path: path.name.lower())

    def _select_model_path(self, model_path: str) -> None:
        if not model_path:
            return
        index = self.model_combo.findData(model_path)
        if index < 0 and Path(model_path).exists():
            self.model_combo.addItem(Path(model_path).name, model_path)
            index = self.model_combo.findData(model_path)
        if index >= 0:
            self.model_combo.setCurrentIndex(index)

    def _model_selected(self) -> None:
        path = self.model_combo.currentData()
        if path:
            self.model_path_input.setText(str(path))

    def _browse_model(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, tr("settings.title_choose_gguf", "Chọn GGUF model"), "", "GGUF models (*.gguf)")
        if file_path:
            self.model_path_input.setText(file_path)
            self._select_model_path(file_path)

    def _refresh_model_info(self) -> None:
        model_path = Path(self.model_path_input.text().strip())
        if not model_path.exists():
            self.model_info.setText(tr("settings.msg_invalid_gguf", "Chưa chọn model GGUF hợp lệ."))
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
        cpu_limit = self.cpu_limit_spin.value()
        limit_text = tr("settings.cpu_no_limit", "không giới hạn") if cpu_limit == 0 else str(min(cpu_limit, cpu))
        parts = [
            tr("settings.cpu_logical", "Logical CPU:") + f" {cpu}",
            tr("settings.ai_threads", "Luồng suy luận LLM") + f": {self.threads_spin.value()}",
            tr("settings.cpu_limit_app", "Giới hạn app:") + f" {limit_text}",
        ]
        if ram_gb:
            parts.append(f"RAM: {ram_gb:.1f} GB")
        if model_size_gb is not None and ram_gb:
            needed = model_size_gb * 1.4
            status = "OK" if ram_gb >= needed else tr("settings.status_ram_insufficient", "RAM có thể không đủ")
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
                self.test_output.setPlainText(tr("settings.msg_local_gguf_invalid", "Local GGUF chưa hợp lệ."))
                return
            self.test_output.setPlainText(
                tr("settings.msg_local_gguf_valid", "Local GGUF hợp lệ. Bấm Load Model để load model, sau đó dùng Generate SQL để test inference.")
            )
            return

        if not config.api_endpoint.strip() or not config.api_model.strip():
            self.test_output.setPlainText(tr("settings.msg_api_required", "API endpoint và API model là bắt buộc."))
            return
        self.test_output.setPlainText(tr("settings.msg_api_valid", "API settings hợp lệ. Bấm Load Model để chọn API model."))

    def _accept_if_valid(self) -> None:
        config = self.config()
        if config.backend == AIBackend.LOCAL:
            path = Path(config.local_model_path)
            if path.suffix.lower() != ".gguf" or not path.exists():
                QMessageBox.warning(self, tr("settings.title_invalid_model", "Model không hợp lệ"), tr("settings.msg_choose_existing_gguf", "Vui lòng chọn file .gguf tồn tại."))
                return
        elif not config.api_endpoint.strip() or not config.api_model.strip():
            QMessageBox.warning(self, tr("settings.title_api_insufficient", "API chưa đủ"), tr("settings.msg_enter_api_endpoint_model", "Vui lòng nhập API endpoint và API model."))
            return
        self.save_requested.emit()

    def _request_load(self) -> None:
        self.load_model_requested.emit(self.config())

    def _request_unload(self) -> None:
        self.unload_model_requested.emit()


class SchemaAnnotationWidget(QWidget):
    """Widget to edit natural-language descriptions for tables and columns in a user-friendly two-pane layout."""

    def __init__(
        self,
        connection_name: str,
        tables: list[TableInfo],
        repository: AnnotationRepository | None = None,
        parent=None,
        show_close_button: bool = False,
    ) -> None:
        super().__init__(parent)
        self.connection_name = connection_name
        self.tables = tables
        self.repository = repository or AnnotationRepository()
        self.annotations = self._merge_annotations()
        self._is_dirty = False
        self._show_close_button = show_close_button

        self.search_input = QLineEdit()
        self.tree = QTreeWidget()
        self.detail_stack = QStackedWidget()
        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)

        self._build_ui()
        self._load_tree()
        self.retranslate_ui()

        self.tree.currentItemChanged.connect(self._on_item_changed)
        self.tree.itemChanged.connect(self._mark_dirty)
        self.search_input.textChanged.connect(self._filter_tree)

    def is_dirty(self) -> bool:
        return self._is_dirty

    def _mark_dirty(self) -> None:
        self._is_dirty = True

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        self.title = QLabel()
        self.title.setObjectName("dialogTitle")
        self.caption = QLabel()
        self.caption.setObjectName("dialogCaption")
        self.caption.setWordWrap(True)
        layout.addWidget(self.title)
        layout.addWidget(self.caption)

        # Main split content area: left lists/tree, right detailed form
        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)

        # Left panel: Search + Tree list
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        self.search_input.setClearButtonEnabled(True)
        left_layout.addWidget(self.search_input)

        self.tree.setColumnCount(2)
        self.tree.setAlternatingRowColors(True)
        self.tree.setRootIsDecorated(True)
        left_layout.addWidget(self.tree, 1)

        # Right panel: Detail form widgets inside stack
        self._build_detail_stack()

        content_layout.addWidget(left_panel, 2)
        content_layout.addWidget(self.detail_stack, 3)
        layout.addLayout(content_layout, 1)

        actions = QHBoxLayout()
        self.save_button = QPushButton()
        self.save_button.setObjectName("primaryButton")
        self.import_button = QPushButton()
        self.import_button.setObjectName("secondaryButton")
        self.export_button = QPushButton()
        self.export_button.setObjectName("secondaryButton")

        self.save_button.clicked.connect(self._save)
        self.import_button.clicked.connect(self._import)
        self.export_button.clicked.connect(self._export)

        actions.addWidget(self.save_button)
        actions.addWidget(self.import_button)
        actions.addWidget(self.export_button)
        actions.addStretch()

        if self._show_close_button:
            self.close_button = QPushButton()
            self.close_button.setObjectName("secondaryButton")
            self.close_button.clicked.connect(self._on_close_clicked)
            actions.addWidget(self.close_button)

        layout.addLayout(actions)
        layout.addWidget(self.status_label)

    def retranslate_ui(self) -> None:
        self.title.setText(tr("settings.annotation_editor_title", "Schema Annotation Editor"))
        self.caption.setText(tr("settings.schema_caption_hint", "Nhập diễn giải tiếng Việt, đơn vị và ghi chú cho cấu trúc dữ liệu. Dữ liệu được lưu trữ độc lập không ảnh hưởng CSDL gốc."))
        self.search_input.setPlaceholderText(tr("settings.schema_search_placeholder", "🔍 Tìm kiếm bảng hoặc cột..."))
        self.tree.setHeaderLabels([
            tr("settings.schema_name_header", "Tên thực tế"),
            tr("settings.schema_desc_header", "Diễn giải")
        ])
        self.save_button.setText(tr("settings.btn_save_annotation", "Save Annotations"))
        self.import_button.setText(tr("settings.btn_import", "Import"))
        self.export_button.setText(tr("settings.btn_export", "Export"))
        if self._show_close_button and hasattr(self, "close_button"):
            self.close_button.setText(tr("dialogs.bookmarks_btn_close", "Đóng"))

        self.placeholder_label.setText(tr("settings.annotation_placeholder", "👈 Chọn một bảng hoặc cột từ danh sách để bắt đầu chỉnh sửa"))
        self.table_desc_label.setText(tr("settings.annotation_table_desc", "Diễn giải bảng:"))
        self.table_desc_edit.setPlaceholderText(tr("settings.annotation_table_placeholder", "Ví dụ: Thông tin tài khoản người dùng"))
        self.column_desc_label.setText(tr("settings.annotation_col_desc", "Diễn giải cột:"))
        self.column_desc_edit.setPlaceholderText(tr("settings.annotation_col_desc_placeholder", "Ví dụ: Mã định danh duy nhất"))
        self.column_unit_label.setText(tr("settings.annotation_col_unit", "Đơn vị (Unit):"))
        self.column_unit_edit.setPlaceholderText(tr("settings.annotation_col_unit_placeholder", "Ví dụ: VND, kg, lượt (nếu có)"))
        self.column_note_label.setText(tr("settings.annotation_col_note", "Ghi chú (Note):"))
        self.column_note_edit.setPlaceholderText(tr("settings.annotation_col_note_placeholder", "Các ghi chú đặc biệt, định dạng hoặc giá trị ví dụ..."))

        self._on_item_changed(self.tree.currentItem(), None)

    def _on_close_clicked(self) -> None:
        # Find the parent QDialog and call accept or reject, triggering closeEvent / discard warning
        parent = self.parent()
        while parent:
            if isinstance(parent, QDialog):
                parent.close()
                break
            parent = parent.parent()

    def _build_detail_stack(self) -> None:
        # Page 0: Empty/Placeholder view
        empty_page = QWidget()
        empty_layout = QVBoxLayout(empty_page)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder_label = QLabel()
        self.placeholder_label.setStyleSheet("color: #64748b; font-style: italic; font-size: 13px;")
        empty_layout.addWidget(self.placeholder_label)
        self.detail_stack.addWidget(empty_page)

        # Page 1: Table details editor form
        table_page = QWidget()
        table_layout = QVBoxLayout(table_page)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(12)

        self.table_title_label = QLabel("Bảng: ...")
        self.table_title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #0f172a;")
        table_layout.addWidget(self.table_title_label)

        table_form = QFormLayout()
        table_form.setSpacing(10)
        self.table_desc_edit = QLineEdit()
        self.table_desc_edit.textChanged.connect(self._on_table_desc_changed)
        self.table_desc_label = QLabel()
        table_form.addRow(self.table_desc_label, self.table_desc_edit)
        table_layout.addLayout(table_form)
        table_layout.addStretch()
        self.detail_stack.addWidget(table_page)

        # Page 2: Column details editor form
        column_page = QWidget()
        column_layout = QVBoxLayout(column_page)
        column_layout.setContentsMargins(0, 0, 0, 0)
        column_layout.setSpacing(12)

        self.column_title_label = QLabel("Cột: ...")
        self.column_title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #0f172a;")
        column_layout.addWidget(self.column_title_label)

        self.column_type_label = QLabel("Kiểu dữ liệu: ...")
        self.column_type_label.setStyleSheet("color: #64748b; font-size: 12px;")
        column_layout.addWidget(self.column_type_label)

        column_form = QFormLayout()
        column_form.setSpacing(10)
        self.column_desc_edit = QLineEdit()
        self.column_desc_edit.textChanged.connect(self._on_column_desc_changed)

        self.column_unit_edit = QLineEdit()
        self.column_unit_edit.textChanged.connect(self._on_column_unit_changed)

        self.column_note_edit = QTextEdit()
        self.column_note_edit.setFixedHeight(120)
        self.column_note_edit.textChanged.connect(self._on_column_note_changed)

        self.column_desc_label = QLabel()
        self.column_unit_label = QLabel()
        self.column_note_label = QLabel()
        column_form.addRow(self.column_desc_label, self.column_desc_edit)
        column_form.addRow(self.column_unit_label, self.column_unit_edit)
        column_form.addRow(self.column_note_label, self.column_note_edit)
        column_layout.addLayout(column_form)
        column_layout.addStretch()
        self.detail_stack.addWidget(column_page)

    def _merge_annotations(self) -> dict[str, object]:
        stored = self.repository.load(self.connection_name)
        baseline = self.repository.empty_for_schema(self.connection_name, self.tables)
        stored_tables = stored.get("tables", {}) if isinstance(stored.get("tables", {}), dict) else {}
        baseline_tables = baseline["tables"]

        for table_name, table_payload in baseline_tables.items():
            existing_table = stored_tables.get(table_name, {})
            if isinstance(existing_table, dict):
                table_payload["description"] = existing_table.get("description", "")
                existing_columns = existing_table.get("columns", {})
                if isinstance(existing_columns, dict):
                    for column_name, column_payload in table_payload["columns"].items():
                        existing_column = existing_columns.get(column_name, {})
                        if isinstance(existing_column, dict):
                            column_payload.update(
                                {
                                    "description": existing_column.get("description", ""),
                                    "unit": existing_column.get("unit", ""),
                                    "note": existing_column.get("note", ""),
                                }
                            )
        return baseline

    def _load_tree(self) -> None:
        self.tree.blockSignals(True)
        self.tree.clear()
        table_payloads = self.annotations.get("tables", {})
        if not isinstance(table_payloads, dict):
            self.tree.blockSignals(False)
            return

        for table in self.tables:
            table_payload = table_payloads.get(table.name, {})
            table_item = QTreeWidgetItem(
                [
                    table.name,
                    str(table_payload.get("description", "")) if isinstance(table_payload, dict) else "",
                    "",  # Unit column (unused visually but holds data for serialization)
                    "",  # Note column (unused visually but holds data for serialization)
                    "TABLE",  # Type column
                ]
            )
            table_item.setData(0, ROLE_KIND, "table")
            table_item.setData(0, ROLE_TABLE, table.name)
            table_item.setToolTip(0, tr("settings.annotation_table_prefix", "Bảng:") + f" {table.name}")
            self.tree.addTopLevelItem(table_item)

            column_payloads = table_payload.get("columns", {}) if isinstance(table_payload, dict) else {}
            for column in table.columns:
                column_payload = column_payloads.get(column.name, {}) if isinstance(column_payloads, dict) else {}
                column_item = QTreeWidgetItem(
                    [
                        column.name,
                        str(column_payload.get("description", "")) if isinstance(column_payload, dict) else "",
                        str(column_payload.get("unit", "")) if isinstance(column_payload, dict) else "",
                        str(column_payload.get("note", "")) if isinstance(column_payload, dict) else "",
                        column.type_name,
                    ]
                )
                column_item.setData(0, ROLE_KIND, "column")
                column_item.setData(0, ROLE_TABLE, table.name)
                column_item.setData(0, ROLE_COLUMN, column.name)
                column_item.setToolTip(0, tr("settings.annotation_column_prefix", "Cột:") + f" {table.name}.{column.name}")
                table_item.addChild(column_item)

        self.tree.collapseAll()
        for index in range(self.tree.columnCount()):
            self.tree.resizeColumnToContents(index)
        self.tree.blockSignals(False)

    def _on_item_changed(self, current: QTreeWidgetItem | None, previous: QTreeWidgetItem | None) -> None:
        if not current:
            self.detail_stack.setCurrentIndex(0)
            return

        kind = current.data(0, ROLE_KIND)
        if kind == "table":
            self.detail_stack.setCurrentIndex(1)
            self.table_title_label.setText(tr("settings.annotation_table_prefix", "Bảng:") + f" {current.text(0)}")
            self.table_desc_edit.blockSignals(True)
            self.table_desc_edit.setText(current.text(1))
            self.table_desc_edit.blockSignals(False)
        elif kind == "column":
            self.detail_stack.setCurrentIndex(2)
            self.column_title_label.setText(tr("settings.annotation_column_prefix", "Cột:") + f" {current.parent().text(0)}.{current.text(0)}")
            self.column_type_label.setText(tr("settings.annotation_data_type", "Kiểu dữ liệu:") + f" {current.text(4)}")
            self.column_desc_edit.blockSignals(True)
            self.column_desc_edit.setText(current.text(1))
            self.column_desc_edit.blockSignals(False)
            self.column_unit_edit.blockSignals(True)
            self.column_unit_edit.setText(current.text(2))
            self.column_unit_edit.blockSignals(False)
            self.column_note_edit.blockSignals(True)
            self.column_note_edit.setPlainText(current.text(3))
            self.column_note_edit.blockSignals(False)
        else:
            self.detail_stack.setCurrentIndex(0)

    def _on_table_desc_changed(self, text: str) -> None:
        current = self.tree.currentItem()
        if current and current.data(0, ROLE_KIND) == "table":
            current.setText(1, text)
            self._mark_dirty()

    def _on_column_desc_changed(self, text: str) -> None:
        current = self.tree.currentItem()
        if current and current.data(0, ROLE_KIND) == "column":
            current.setText(1, text)
            self._mark_dirty()

    def _on_column_unit_changed(self, text: str) -> None:
        current = self.tree.currentItem()
        if current and current.data(0, ROLE_KIND) == "column":
            current.setText(2, text)
            self._mark_dirty()

    def _on_column_note_changed(self) -> None:
        current = self.tree.currentItem()
        if current and current.data(0, ROLE_KIND) == "column":
            current.setText(3, self.column_note_edit.toPlainText())
            self._mark_dirty()

    def _filter_tree(self, text: str) -> None:
        query = text.strip().lower()
        self.tree.blockSignals(True)

        for table_index in range(self.tree.topLevelItemCount()):
            table_item = self.tree.topLevelItem(table_index)
            table_name = table_item.text(0).lower()
            table_desc = table_item.text(1).lower()

            table_matches = (query in table_name) or (query in table_desc)
            any_column_matches = False

            for column_index in range(table_item.childCount()):
                column_item = table_item.child(column_index)
                column_name = column_item.text(0).lower()
                column_desc = column_item.text(1).lower()
                column_unit = column_item.text(2).lower()
                column_note = column_item.text(3).lower()

                column_matches = (
                    (query in column_name)
                    or (query in column_desc)
                    or (query in column_unit)
                    or (query in column_note)
                )

                if column_matches:
                    column_item.setHidden(False)
                    any_column_matches = True
                else:
                    column_item.setHidden(True)

            if table_matches or any_column_matches:
                table_item.setHidden(False)
                table_item.setExpanded(bool(query))
            else:
                table_item.setHidden(True)

        self.tree.blockSignals(False)

    def _collect_annotations(self) -> dict[str, object]:
        tables: dict[str, object] = {}
        for table_index in range(self.tree.topLevelItemCount()):
            table_item = self.tree.topLevelItem(table_index)
            table_name = table_item.data(0, ROLE_TABLE)
            table_payload = {"description": table_item.text(1).strip(), "columns": {}}
            for column_index in range(table_item.childCount()):
                column_item = table_item.child(column_index)
                column_name = column_item.data(0, ROLE_COLUMN)
                table_payload["columns"][column_name] = {
                    "description": column_item.text(1).strip(),
                    "unit": column_item.text(2).strip(),
                    "note": column_item.text(3).strip(),
                    "type": column_item.text(4).strip(),
                }
            tables[table_name] = table_payload
        return {"connection_name": self.connection_name, "tables": tables}

    def _save(self) -> None:
        self.annotations = self._collect_annotations()
        path = self.repository.save(self.connection_name, self.annotations)
        self._is_dirty = False
        self.status_label.setText(tr("settings.msg_annotations_saved", "Đã lưu annotations: ") + f"{path}")

    def _import(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, tr("settings.title_import_annotations", "Import annotations"), "", "JSON (*.json);;All files (*.*)")
        if not file_path:
            return
        try:
            with Path(file_path).open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except (OSError, json.JSONDecodeError) as exc:
            QMessageBox.warning(self, tr("settings.title_import_error", "Import lỗi"), str(exc))
            return
        self.annotations = payload
        self._load_tree()
        self._is_dirty = True
        self.status_label.setText(tr("settings.msg_annotations_imported", "Đã import annotations."))

    def _export(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(self, tr("settings.title_export_annotations", "Export annotations"), f"{self.connection_name}.annotations.json", "JSON (*.json)")
        if not file_path:
            return
        payload = self._collect_annotations()
        try:
            with Path(file_path).open("w", encoding="utf-8") as file:
                json.dump(payload, file, ensure_ascii=False, indent=2)
        except OSError as exc:
            QMessageBox.warning(self, tr("settings.title_export_error", "Export lỗi"), str(exc))
            return
        self.status_label.setText(tr("settings.msg_annotations_exported", "Đã export annotations."))


class SettingsDialog(QDialog):
    """Consolidated main Settings Dialog containing AI backend settings and schema annotations."""

    load_model_requested = Signal(AIModelConfig)
    unload_model_requested = Signal()

    def __init__(
        self,
        config: AIModelConfig,
        connection_name: str,
        tables: list[TableInfo],
        repository: AnnotationRepository | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setMinimumSize(960, 640)
        self.setModal(True)

        self.nav_list = QListWidget()
        self.nav_list.setFixedWidth(180)
        self.nav_list.setStyleSheet("""
            QListWidget {
                background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 10px;
                border-radius: 5px;
                font-weight: 500;
                color: #475569;
            }
            QListWidget::item:selected {
                background-color: #edf6ff;
                color: #0f62fe;
            }
        """)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet("""
            QStackedWidget {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 16px;
            }
        """)

        # Add child widgets
        self.ai_widget = AISettingsWidget(config, self)
        self.ai_widget.load_model_requested.connect(self.load_model_requested.emit)
        self.ai_widget.unload_model_requested.connect(self.unload_model_requested.emit)
        self.ai_widget.save_requested.connect(self.accept)

        self.schema_widget = SchemaAnnotationWidget(connection_name, tables, repository, self)

        self.stack.addWidget(self.ai_widget)
        self.stack.addWidget(self.schema_widget)

        self.nav_list.currentRowChanged.connect(self.stack.setCurrentIndex)

        self._build_ui()
        self.retranslate_ui()
        self.nav_list.setCurrentRow(0)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(tr("settings.settings_title", "Settings"))
        
        self.nav_list.blockSignals(True)
        self.nav_list.clear()
        self.nav_list.addItem(tr("settings.tab_ai_config", "Cài đặt AI"))
        self.nav_list.addItem(tr("settings.tab_schema_annotation", "Chú thích CSDL"))
        self.nav_list.blockSignals(False)
        
        self.ai_widget.retranslate_ui()
        self.schema_widget.retranslate_ui()

    def _build_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)
        left_layout.addWidget(self.nav_list, 1)

        main_layout.addWidget(left_panel)
        main_layout.addWidget(self.stack, 1)

    def config(self) -> AIModelConfig:
        return self.ai_widget.config()

    def closeEvent(self, event) -> None:
        if self._confirm_discard_changes():
            event.accept()
        else:
            event.ignore()

    def _confirm_discard_changes(self) -> bool:
        if self.schema_widget.is_dirty():
            res = QMessageBox.question(
                self,
                tr("settings.title_unsaved_changes", "Có thay đổi chưa lưu"),
                tr("settings.msg_unsaved_changes", "Bạn có thay đổi chưa lưu trong Chú thích Schema. Bạn có chắc chắn muốn quay lại và bỏ qua thay đổi?"),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            return res == QMessageBox.Yes
        return True

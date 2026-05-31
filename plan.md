# Kế hoạch chi tiết: 4.4 - Hoàn thiện vòng lặp tự sửa lỗi (Self-Correction)

## 1. Mục tiêu

Xây dựng vòng lặp tự động trong đó AI Agent:
1. Sinh câu lệnh SQL từ câu hỏi.
2. Thực thi câu lệnh (chỉ SELECT) và bắt lỗi.
3. Nếu có lỗi → đưa thông báo lỗi vào prompt → yêu cầu model sửa.
4. Lặp lại tối đa N lần (mặc định 3).
5. Trả về kết quả thành công hoặc thông báo thất bại.

---

## 2. Phân tích hiện trạng trong repo

### 2.1. Những gì đã có

Trong `services/text_to_sql_pipeline.py`, hiện tại đã có:

```python
class TextToSqlPipeline:
    def generate_sql(self, question: str, db_connection=None, 
                     error_message: str = None, max_retries: int = 3):
        # Đã có tham số error_message và max_retries
        # Nhưng chưa có cơ chế tự động thực thi và bắt lỗi
```

**Vấn đề**: 
- `error_message` phải được truyền từ bên ngoài.
- Không có vòng lặp tự động gọi lại `generate_sql` khi có lỗi.
- Không có module thực thi SQL an toàn trong pipeline.

### 2.2. Những gì cần thêm

1. **SQL Executor an toàn** (chỉ SELECT, bắt exception).
2. **Vòng lặp tự động** trong `TextToSqlPipeline`.
3. **Tích hợp với AI Engine** để regenerate khi có lỗi.
4. **Logging và monitoring** để debug.

---

## 3. Chi tiết các bước thực hiện

### Bước 4.4.1: Tạo module SQL Executor an toàn

**File**: `services/sql_executor.py` (mới)

```python
"""
SQL Executor - Chỉ cho phép SELECT statements
"""
import re
from typing import Dict, Any, List, Tuple
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
import logging

logger = logging.getLogger(__name__)

class SafeSQLExecutor:
    """Thực thi SQL an toàn, chỉ cho phép SELECT"""
    
    def __init__(self, connection_string: str):
        """
        Args:
            connection_string: SQLAlchemy connection string
        """
        self.engine = create_engine(connection_string)
        self.forbidden_keywords = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 
                                   'ALTER', 'CREATE', 'TRUNCATE', 'MERGE']
    
    def validate_sql(self, sql: str) -> Tuple[bool, str]:
        """
        Kiểm tra câu lệnh SQL có an toàn không
        
        Returns:
            (is_valid, error_message)
        """
        sql_upper = sql.strip().upper()
        
        # Chỉ cho phép SELECT
        if not sql_upper.startswith('SELECT'):
            return False, "Only SELECT queries are allowed"
        
        # Kiểm tra từ khóa nguy hiểm
        for keyword in self.forbidden_keywords:
            if re.search(rf'\b{keyword}\b', sql_upper):
                return False, f"Forbidden keyword detected: {keyword}"
        
        return True, ""
    
    def execute(self, sql: str) -> Dict[str, Any]:
        """
        Thực thi câu lệnh SELECT
        
        Args:
            sql: Câu lệnh SQL (phải bắt đầu bằng SELECT)
            
        Returns:
            Dictionary với keys: 'success', 'data', 'error', 'columns'
        """
        # Validate
        is_valid, error_msg = self.validate_sql(sql)
        if not is_valid:
            return {
                'success': False,
                'error': error_msg,
                'data': None,
                'columns': []
            }
        
        # Execute
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(sql))
                rows = result.fetchall()
                columns = list(result.keys())
                
                # Convert rows to list of dicts hoặc list of lists
                data = [dict(zip(columns, row)) for row in rows]
                
                return {
                    'success': True,
                    'error': None,
                    'data': data,
                    'columns': columns,
                    'row_count': len(data)
                }
        except SQLAlchemyError as e:
            error_msg = str(e)
            logger.error(f"SQL execution error: {error_msg}\nSQL: {sql}")
            return {
                'success': False,
                'error': error_msg,
                'data': None,
                'columns': []
            }
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'data': None,
                'columns': []
            }
```

### Bước 4.4.2: Cập nhật TextToSqlPipeline

**File**: `services/text_to_sql_pipeline.py` (sửa)

```python
from services.sql_executor import SafeSQLExecutor
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class TextToSqlPipeline:
    def __init__(self, db_connector, ai_engine, embedding_model=None, 
                 use_neural_embedding=True, max_retries=3):
        # ... existing code ...
        self.max_retries = max_retries
        self.sql_executor = None  # Will be initialized when DB connected
        
    def set_database_connection(self, connection_string: str):
        """Thiết lập kết nối database và SQL executor"""
        self.sql_executor = SafeSQLExecutor(connection_string)
        
    def execute_with_self_correction(self, question: str, 
                                     connection_string: str,
                                     max_retries: Optional[int] = None) -> Dict[str, Any]:
        """
        Thực thi pipeline với vòng lặp tự sửa lỗi
        
        Args:
            question: Câu hỏi bằng ngôn ngữ tự nhiên
            connection_string: Kết nối database
            max_retries: Số lần thử tối đa (mặc định = self.max_retries)
            
        Returns:
            Dictionary với keys:
                - success: bool
                - sql: str (câu lệnh cuối cùng)
                - result: data (nếu success)
                - error: str (nếu thất bại)
                - attempts: int (số lần đã thử)
                - error_history: list (các lỗi gặp phải)
        """
        if max_retries is None:
            max_retries = self.max_retries
            
        # Khởi tạo SQL executor
        self.set_database_connection(connection_string)
        
        error_history = []
        last_error = None
        
        for attempt in range(max_retries):
            logger.info(f"Attempt {attempt + 1}/{max_retries} for question: {question[:50]}...")
            
            # Bước 1: Generate SQL (có thể có error_message từ lần trước)
            try:
                sql = self.generate_sql(
                    question=question,
                    error_message=last_error,
                    max_retries=1  # Chỉ generate 1 lần trong vòng lặp này
                )
            except Exception as e:
                error_msg = f"SQL generation failed: {str(e)}"
                logger.error(error_msg)
                error_history.append(error_msg)
                last_error = error_msg
                continue
            
            # Bước 2: Validate và execute
            if not sql:
                error_msg = "Generated SQL is empty"
                error_history.append(error_msg)
                last_error = error_msg
                continue
            
            logger.debug(f"Generated SQL: {sql}")
            
            # Bước 3: Thực thi
            exec_result = self.sql_executor.execute(sql)
            
            if exec_result['success']:
                # Thành công
                return {
                    'success': True,
                    'sql': sql,
                    'result': exec_result['data'],
                    'columns': exec_result['columns'],
                    'row_count': exec_result['row_count'],
                    'attempts': attempt + 1,
                    'error_history': error_history
                }
            else:
                # Thất bại - lưu lỗi để retry
                error_msg = exec_result['error']
                error_history.append(error_msg)
                last_error = error_msg
                logger.warning(f"Attempt {attempt + 1} failed: {error_msg}")
                
                # Tiếp tục vòng lặp
        
        # Hết số lần thử
        return {
            'success': False,
            'sql': None,
            'result': None,
            'error': f"Failed after {max_retries} attempts. Last error: {last_error}",
            'attempts': max_retries,
            'error_history': error_history
        }
    
    def generate_sql(self, question: str, error_message: str = None, 
                     max_retries: int = 1) -> str:
        """
        Sinh câu lệnh SQL (có thể có error_message từ lần trước)
        
        Args:
            question: Câu hỏi
            error_message: Thông báo lỗi từ lần thực thi trước (nếu có)
            max_retries: Số lần generate tối đa (mặc định 1)
        """
        # Existing code for schema linking, prompt building, etc.
        # ...
        
        # Xây dựng prompt (có error_message nếu có)
        prompt = self.prompt_builder.build_prompt(
            question=question,
            schema_subset=schema_subset,
            few_shot_examples=self.get_few_shot_examples(question),
            error_message=error_message  # Quan trọng: truyền lỗi vào prompt
        )
        
        # Gọi AI Engine
        sql = self.ai_engine.generate(prompt)
        
        # Trích xuất SQL từ response (nếu cần)
        sql = self.extract_sql_from_response(sql)
        
        return sql
    
    def extract_sql_from_response(self, response: str) -> str:
        """Trích xuất câu lệnh SQL từ response của model"""
        import re
        
        # Tìm code block SQL
        sql_pattern = r'```sql\n(.*?)\n```'
        match = re.search(sql_pattern, response, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        # Nếu không có code block, tìm dòng bắt đầu bằng SELECT
        lines = response.strip().split('\n')
        for line in lines:
            if line.strip().upper().startswith('SELECT'):
                return line.strip()
        
        # Trả về toàn bộ response (có thể là SQL)
        return response.strip()
```

### Bước 4.4.3: Cập nhật PromptBuilder để hỗ trợ error message

**File**: `services/prompt_builder.py` (sửa)

```python
class PromptBuilder:
    def __init__(self):
        self.default_system_prompt = """You are an expert SQL generator. Generate ONLY a valid SELECT SQL statement for the given schema. Do not include any explanation."""
        
        # Template cho error correction
        self.error_correction_template = """
The previous SQL query failed with the following error:
{error_message}

Please correct the SQL query. Make sure to:
1. Check table and column names (they must exist in the schema)
2. Verify data types in conditions
3. Ensure JOIN conditions are correct
4. Remove any syntax errors

Generate ONLY the corrected SELECT SQL statement.
"""
    
    def build_prompt(self, question: str, schema_subset, 
                     few_shot_examples=None, error_message=None,
                     use_skeleton=False) -> str:
        """Xây dựng prompt hoàn chỉnh"""
        
        parts = []
        
        # System prompt
        if use_skeleton:
            parts.append(self.skeleton_system_prompt)
        else:
            parts.append(self.default_system_prompt)
        
        # Schema
        parts.append("\n\n## Database Schema:")
        parts.append(self.format_schema(schema_subset))
        
        # Few-shot examples
        if few_shot_examples:
            parts.append("\n\n## Examples:")
            for ex in few_shot_examples:
                parts.append(f"Question: {ex['question']}")
                parts.append(f"SQL: {ex['sql']}")
        
        # Error message (nếu có) - QUAN TRỌNG CHO SELF-CORRECTION
        if error_message:
            parts.append("\n\n## Error Correction Required:")
            parts.append(self.error_correction_template.format(error_message=error_message))
        
        # Current question
        parts.append(f"\n\n## Question: {question}")
        parts.append("SQL:")
        
        return "\n".join(parts)
```

### Bước 4.4.4: Cập nhật AI Engine để hỗ trợ regenerate

**File**: `services/ai_engine.py` (thêm method)

```python
class AIEngine:
    # ... existing code ...
    
    def generate_with_retry(self, prompt: str, max_retries: int = 1) -> str:
        """
        Generate với khả năng retry nếu kết quả rỗng hoặc không hợp lệ
        """
        for attempt in range(max_retries):
            result = self.generate(prompt)
            if result and len(result.strip()) > 0:
                # Kiểm tra sơ bộ: có chứa SELECT không?
                if 'SELECT' in result.upper():
                    return result
                elif attempt == max_retries - 1:
                    # Lần cuối, vẫn trả về dù không có SELECT
                    return result
            # Chờ một chút nếu cần (cho API)
            if attempt < max_retries - 1:
                import time
                time.sleep(0.5)
        return ""
```

### Bước 4.4.5: Tích hợp vào Controller (UI)

**File**: `controllers/query_controller.py` (sửa)

```python
class QueryController:
    def __init__(self):
        self.pipeline = None
        self.current_connection = None
    
    def execute_natural_language_query(self, question: str, db_config: dict) -> dict:
        """
        Xử lý câu hỏi từ UI với self-correction
        """
        try:
            # Tạo connection string từ config
            conn_string = self.build_connection_string(db_config)
            
            # Khởi tạo pipeline nếu chưa có
            if not self.pipeline:
                self.pipeline = TextToSqlPipeline(
                    db_connector=...,
                    ai_engine=self.ai_engine,
                    max_retries=3  # Mặc định 3 lần
                )
            
            # Thực thi với self-correction
            result = self.pipeline.execute_with_self_correction(
                question=question,
                connection_string=conn_string
            )
            
            # Log kết quả
            if result['success']:
                logger.info(f"Success after {result['attempts']} attempts")
                if result['attempts'] > 1:
                    logger.info(f"Error history: {result['error_history']}")
            else:
                logger.error(f"Failed after {result['attempts']} attempts: {result['error']}")
            
            return result
            
        except Exception as e:
            logger.exception("Unexpected error in query execution")
            return {
                'success': False,
                'error': f"System error: {str(e)}",
                'sql': None,
                'result': None
            }
```

### Bước 4.4.6: Thêm logging và monitoring

**File**: `utils/query_logger.py` (mới)

```python
"""
Query logging để debug self-correction
"""
import json
from datetime import datetime
from pathlib import Path
import logging

class QueryLogger:
    def __init__(self, log_dir="logs/queries"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
    
    def log_query_attempt(self, question: str, attempt: int, 
                          sql: str, error: str = None, 
                          success: bool = False):
        """Ghi lại mỗi lần thử"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'question': question,
            'attempt': attempt,
            'sql': sql,
            'error': error,
            'success': success
        }
        
        # Lưu vào file JSON
        log_file = self.log_dir / f"{datetime.now().strftime('%Y%m%d')}.json"
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        
        # Log vào console
        if success:
            self.logger.info(f"Attempt {attempt} SUCCESS")
        else:
            self.logger.warning(f"Attempt {attempt} FAILED: {error}")
    
    def get_statistics(self, days=7):
        """Thống kê tỷ lệ thành công của self-correction"""
        # Implementation để phân tích hiệu quả
        pass
```

### Bước 4.4.7: Cập nhật configuration

**File**: `config.yaml` (thêm section)

```yaml
self_correction:
  enabled: true
  max_retries: 3
  log_errors: true
  retry_delay_seconds: 0.5
  include_error_in_prompt: true
  stop_on_syntax_error: false  # Nếu true, dừng ngay khi lỗi syntax
```

---

## 4. Testing

### 4.1. Unit test cho SQL Executor

**File**: `tests/test_sql_executor.py`

```python
import pytest
from services.sql_executor import SafeSQLExecutor

def test_validate_select():
    executor = SafeSQLExecutor("sqlite:///:memory:")
    is_valid, error = executor.validate_sql("SELECT * FROM users")
    assert is_valid == True
    assert error == ""

def test_reject_insert():
    executor = SafeSQLExecutor("sqlite:///:memory:")
    is_valid, error = executor.validate_sql("INSERT INTO users VALUES (1)")
    assert is_valid == False
    assert "INSERT" in error

def test_execute_invalid_sql():
    executor = SafeSQLExecutor("sqlite:///:memory:")
    result = executor.execute("SELECT * FROM nonexistent_table")
    assert result['success'] == False
    assert "no such table" in result['error'].lower()
```

### 4.2. Integration test cho self-correction

**File**: `tests/test_self_correction.py`

```python
def test_self_correction_handles_typo():
    """Test model tự sửa lỗi chính tả tên cột"""
    pipeline = TextToSqlPipeline(...)
    
    # Câu hỏi có thể dẫn đến lỗi typo
    result = pipeline.execute_with_self_correction(
        question="Hiển thị tên khách hàng",
        connection_string="sqlite:///test.db"
    )
    
    # Kiểm tra đã thử ít nhất 2 lần
    assert result['attempts'] >= 2
    assert result['success'] == True

def test_self_correction_max_retries():
    """Test dừng lại sau max_retries lần thất bại"""
    pipeline = TextToSqlPipeline(..., max_retries=2)
    
    # Giả lập model luôn sinh SQL sai
    # ...
    
    result = pipeline.execute_with_self_correction(...)
    assert result['success'] == False
    assert result['attempts'] == 2
```

---

## 5. Triển khai và monitoring

### 5.1. Metrics cần theo dõi

Sau khi triển khai, theo dõi các metrics:

| Metric | Ý nghĩa | Mục tiêu |
|--------|---------|----------|
| `success_rate` | Tỷ lệ query thành công sau N lần | >85% |
| `avg_attempts` | Số lần thử trung bình | <1.5 |
| `error_types` | Phân loại lỗi (syntax, schema, logic) | Để cải thiện prompt |
| `correction_rate` | Tỷ lệ lỗi được sửa thành công | >60% |

### 5.2. Xử lý edge cases

1. **Lỗi syntax liên tục**: Nếu cùng một lỗi lặp lại, dừng sớm.
2. **Timeout**: Thêm timeout cho mỗi lần thực thi (30 giây).
3. **Memory leak**: Giải phóng connection sau mỗi lần thử.

### 5.3. Fallback strategy

Nếu self-correction thất bại sau 3 lần:

```python
if not result['success']:
    # Option 1: Trả về câu SQL cuối cùng (dù sai) để người dùng sửa tay
    # Option 2: Gửi thông báo lỗi chi tiết
    # Option 3: Gọi một model mạnh hơn qua API (nếu có)
    return {
        'fallback_used': True,
        'suggested_sql': last_sql,
        'error': last_error
    }
```

---

## 6. Tài liệu hướng dẫn sử dụng

**File**: `docs/SELF_CORRECTION.md`

```markdown
# Self-Correction Feature

## Cách hoạt động
1. AI sinh SQL từ câu hỏi
2. Hệ thống thử chạy SQL
3. Nếu lỗi → thông báo lỗi được đưa vào prompt
4. AI sinh lại SQL đã sửa
5. Lặp lại tối đa 3 lần

## Cấu hình
Trong Settings → Advanced:
- Max Retries: 1-5 (mặc định 3)
- Log Errors: Bật/tắt ghi log

## Best practices
- Với database lớn, nên bật self-correction
- Nếu query quá phức tạp, có thể cần retry nhiều hơn
- Xem log tại `logs/queries/` để debug
```

---

## 7. Kết luận

Sau khi hoàn thành plan 4.4, dự án sẽ có:

✅ **Vòng lặp tự động** từ generate → execute → catch error → regenerate.  
✅ **Safe SQL executor** chỉ cho phép SELECT.  
✅ **Prompt được cập nhật** với error message để model tự sửa.  
✅ **Logging chi tiết** để debug và monitoring.  
✅ **Configurable** qua file YAML.

**Kết quả kỳ vọng**: Giảm 30–40% lỗi thực thi, tăng độ tin cậy tổng thể lên 85%+ cho các câu hỏi phổ biến.

Bạn có muốn tôi viết script tự động áp dụng các thay đổi này vào repo không?
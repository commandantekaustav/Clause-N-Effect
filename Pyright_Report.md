# 📋 Pyright Quality Report

**Total Files Checked:** 30  
**Total Errors:** 8  
**Total Warnings:** 0  

## 🔍 Issue Details

| File | Line | Severity | Message |
| --- | --- | --- | --- |
| evolve_prompts.py | 54 | 🔴 ERROR | Argument of type "str" cannot be assigned to parameter "api_key" of type "SecretStr | None" in function "__init__" ┬á┬áType "str" is not assignable to type "SecretStr | None" ┬á┬á┬á┬á"str" is not assignable to "SecretStr" ┬á┬á┬á┬á"str" is not assignable to "None" |
| logger.py | 23 | 🔴 ERROR | Expression of type "None" cannot be assigned to parameter of type "list[Unknown]" ┬á┬á"None" is not assignable to "list[Unknown]" |
| parser.py | 17 | 🔴 ERROR | Argument of type "str | None" cannot be assigned to parameter "value" of type "str" in function "__setitem__" ┬á┬áType "str | None" is not assignable to type "str" ┬á┬á┬á┬á"None" is not assignable to "str" |
| parser.py | 56 | 🔴 ERROR | Argument of type "Literal['markdown']" cannot be assigned to parameter "result_type" of type "ResultType" in function "__init__" ┬á┬á"Literal['markdown']" is not assignable to "ResultType" |
| src\agents\graph.py | 28 | 🔴 ERROR | Argument of type "str | None" cannot be assigned to parameter "secret_value" of type "str" in function "__init__" ┬á┬áType "str | None" is not assignable to type "str" ┬á┬á┬á┬á"None" is not assignable to "str" |
| src\tools\retriever.py | 79 | 🔴 ERROR | Cannot access attribute "_dict" for class "Docstore" ┬á┬áAttribute "_dict" is unknown |
| src\utils\stream_handler.py | 102 | 🔴 ERROR | "final_revisions" is possibly unbound |
| src\utils\stream_handler.py | 102 | 🔴 ERROR | "final_rejection_reasons" is possibly unbound |

# Traceability Matrix

| Requirement | Prompt | Primary implementation | Primary tests |
| --- | --- | --- | --- |
| REQ-P5-01 | `REQ-P5-01-output-serialization.md` | `router/output/writer.py`, `main.py` | `test_output_writer.py`, `test_output_pipeline_integration.py`, `test_submission_system.py` |
| REQ-P5-03 | `REQ-P5-03-output-field-validation.md` | `router/output/validation.py`, `router/errors.py` | `test_output_validation.py`, `test_output_pipeline_integration.py`, `test_submission_system.py` |
| REQ-P5-02 | `REQ-P5-02-sample-calibration.md` | `router/output/calibration.py`, `main.py`, `README.md` | `test_calibration.py`, `test_calibration_integration.py`, `test_submission_system.py` |
| REQ-P5-04 | `REQ-P5-04-reproducible-submission-command.md` | `main.py`, `README.md` | `test_submission_command.py`, `test_submission_system.py` |

Every named test is marked with its corresponding requirement id. API tests
are N/A unless they prove the existing OCR/ASR environment-key boundary; no
new API is introduced. UI tests are N/A because the deliverable is a batch
CSV, while the README command and calibration text receive documentation
acceptance checks.

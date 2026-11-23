# Deterministic scoring core for cloud security and privacy risk assessment (research prototype)

Code and data of the paper "Evidence-Aware Deterministic Scoring Core for Cloud Security and Privacy Risk Assessment: Design and Preliminary Evaluation (A Lightweight Tool for SMEs)".

Synthetic scenarios only. The output is decision support that requires human review and makes no claim of legal compliance.

## Layout
- `src/engine.py`: scoring engine (standard library only, integer arithmetic, no randomness, no external calls).
- `repository.json`: 35 indicators, 7 domains, impact weights and source references (Tables A1 to A4 of the paper). `tools/verify_repository.py` checks it against the text of Section 4 in `spec/`.
- `scenarios/S1.json ... S8.json`: the eight synthetic scenarios, built by `tools/build_scenarios.py` from Table B1. `FREEZE_MANIFEST.json` holds their SHA-256 values.
- `tests/test_engine.py`: automated verification V1 to V11 (69 tests). `tests/test_web.py`: smoke tests of the Django layer (3 tests).
- `webapp/`: Django and SQLite input form and report page. The engine is imported as a separate module.
- `manual/`: the separately written reference implementation (`reference_calc.py`) and its dated result file. It is not a calculation by hand.
- `tools/run_evaluation.py`: scenario runs, paired personal-data test, sensitivity analysis (528 runs) and comparison with the reference implementation. Output is written to `results/`.
- `spec/`: text of Sections 4 and 5 as fixed before the runs, used to build and verify the inputs. `DEVIATIONS.md` lists all deviations and corrections.

## Reproduce
    pip install django pytest
    python tools/verify_repository.py
    python -m pytest tests -q
    python tools/run_evaluation.py > results/console.txt
    python tools/make_tables.py
    cd webapp
    python manage.py migrate
    python manage.py runserver

On Linux or macOS use `python3` instead of `python`.

## Rounding
Metrics are stored as an integer numerator and denominator. Display values are rounded half up to one decimal place using integer arithmetic. Exact ties are flagged (`exact_rounding_tie`).

## Scope and limits
The results concern the conformity and behavior of the implementation on synthetic inputs. They do not show predictive validity, correct weights for real organizations or legal compliance. The usability evaluation was not conducted.

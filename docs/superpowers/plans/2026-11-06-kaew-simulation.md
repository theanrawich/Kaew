# Kaew simulation implementation plan

1. Define and test a deterministic, fail-safe controller and simulated water plant; use virtual time and fault injection.
2. Connect the controller to a local interactive 3D view and readable state / event log, clearly labelled simulated.
3. Add simulated node to gateway to local telemetry pipeline and inspectable dashboard; test failures and recovery.
4. Audit CAD component dimensions against existing source register and disclose unknowns. Do not silently assert mechanical fit.
5. Run automated and browser checks, record precisely what has and has not been verified. Real firmware, sensors, pump and safety remain physical verification tasks.

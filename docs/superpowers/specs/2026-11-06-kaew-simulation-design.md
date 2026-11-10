# Kaew software simulation: working design

Build a local, reproducible digital prototype before purchasing hardware. Simulated inputs and outputs must be clearly identified. Use one controller state for simulated sensors, pump, data views and the interactive 3D model. The existing CAD is reference geometry, with unverified dimensions identified rather than presented as measured. Flow sensor is excluded.

The controller must reject invalid targets and stop on cup removal, stop button, stale or failed sensor data, empty reservoir, or timeout. A simulated pump must default off after restart. Cloud, voice, AI and hardware tests must not be implied by a simulation. Record assumptions and test normal, boundary and fault conditions. Physical pump interface, independent stop circuit, wet materials and actual dimensions remain to be verified.

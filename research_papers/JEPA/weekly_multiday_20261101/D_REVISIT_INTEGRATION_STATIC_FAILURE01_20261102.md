# D synthetic producer/auditor agreement: first fixture candidate rejected

Status: FIX_FIRST_STATIC_ONLY. No integration execution occurred.

Root preserved test_weekly_zone_revisit_mechanics_integration.py9856B,
584dbc40157ff02920b98a564ff02a0bc94eb8929e1c1bcab4cbcb4605c93797,
in REANUDACION_20261102/d_integration_static_candidate01.

Reviewer `/root/d_integration_static_review` found that the three-day same-plan
case does not establish B-only lockout after an A exit: the A target is not
reached until day2 and no usable exit bid arrives before H2. Both arms therefore
remain open at the later entries. Replace that fixture with two plans where
the first plan A exits at D10:38 and the second plan enters next session while
the first B remains open. Assert all four second-plan WAIT/OPEN_POSITION rows
and independent before-entry balances A/BASE104483.8, A/ADVERSE104389.8,
B/BASE95191.9 and B/ADVERSE95144.9, then require complete auditor agreement.

Other reviewed cases are sound: baseline four-book manual values and public
projection shapes, PUT STOP with missing-bid commission, missing geometry and
mixed historical coverage, and mutation rejection for IDs/clocks/net/counts.
The integration test author reads only public auditor API signatures and never
the independent implementation or its tests. The independent author must not
read these integration fixtures while its own implementation remains pending.

These are new cross-implementation agreement checks, not repetitions of the
closed component suites. They may run only after the independent auditor's
own reviewed formal suite closes, with their own reviewed published harness
and observed resource gates. No real adapter or B/C/D market input is admitted.

# Weekly zone-event value-path V2 audit runtime binding

Status: `FINAL_CANDIDATE_REQUIRES_REVIEW_AND_PUBLICATION`  
Date: 2026-11-02

This binding authorizes one independent audit child only after byte-exact
publication and contemporaneous resource gates. It authorizes no producer
rerun, economic interpretation, selection or promotion.

Frozen auditor: `audit_weekly_zone_event_value_paths_v2.py`, 112,984 bytes,
SHA `1ad942249d2eb160b2e8fe1ed902e577f9617dc4c11575e297cf5262f5aa61f2`.
Tests: 36,968 bytes, SHA
`e7f7c6e7cd7f9b93a1763b969205478da87182247b1d284d7c9fd5b980112bf7`.
Final review: 2,437 bytes, SHA
`161edabbf3783b99efc7431ec00fae7c129cbf56551f2998acd2cd99dd69c2fe`.
The formal suite passed 70 tests. Contract amendment SHA is
`65fd1aaef25ddea13957ce07e6c21285771adc889f097d603f93e00572cf1146`.

Producer02 is immutable: manifest 3,134,113 bytes SHA
`a30376cec17aa649b2869efe1bba8f4a19f901e3a10399942df70c7fe2a42f33`;
retained exit 358 bytes SHA
`06af66e622ce1119f04c2c496b161660abd897a02ecdb902dd71d39b26eb2dc3`.
Its compact closure archive has manifest 8,727 bytes SHA
`2161419b29df6fff7cd2c3fccffc226070422ea4fff56f721f1f665f285d924c`
and receipt 778 bytes SHA
`11448ef0f9b041a01b73c2182ad1c1e7c97d4d1b1727f7e489583c4d7cbdf780`.
The launcher additionally binds all eight live producer outputs from that
manifest by exact path, bytes and SHA-256 and rehashes them at admission,
immediately pre-child and closure; the manifest alone is not a substitute.

The exclusive fresh roots are
`D:\GexResearchArtifacts\weekly_multiday_20261101\weekly_zone_event_value_paths_audit_02`
and `...\weekly_zone_event_value_paths_audit_observer_02`. The launcher must
retain its own process evidence under the separate fresh
`...\weekly_zone_event_value_paths_audit_launcher_observer_02`, because the
auditor itself requires and creates audit_observer02 atomically. The launcher must
verify repository publication, producer manifest/exit, all 29 authority inputs,
producer outputs and closure archive pins before a hidden CPU0 child. It sets
the ten thread variables to 1, disables CUDA, applies the official RAM/commit
gate and D: >=2GB gate immediately pre-child, retains PID/creation/logs/exit,
and rehashes all pins at closure. No retry or partial adoption.

Exact auditor CLI arguments are `--execute-reviewed-audit`, producer root and
manifest SHA, producer exit and SHA, auditor/tests SHA, and exact path/bytes/SHA
triples for review, runtime binding and launcher, followed by output and observer.
Only an audit exit 0 and its complete retained evidence can authorize later
interpretation; this binding itself makes no economic claim.

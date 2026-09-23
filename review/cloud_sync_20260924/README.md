# 非论文项目快照上传清单（2026-09-24）

**这是部分备份，不是全量上传。第二轮已完成；上传仍有大文件问题，暂不关机。**

GitHub LFS 对 acc_n02.abq（4,402,044,928 字节）的 batch 请求已明确返回 422：单文件必须 ≤2,147,483,648 字节。完整项目数据约 94 GiB，本地剩余约 9 GiB，不能一次性生成完整 LFS 对象副本。未购买额度或删除原始结果。

本次包含代码、交接与指标、PPT/讲解稿、GIF/PNG、NPZ/CSV、输入 deck、诊断读数以及低于 100 MiB 的已保存求解器文件。≥100 MiB 的原始求解器文件等待确定容量与存储方案；并非这些文件全部超过远端单文件上限。具体范围以 JSON 逐文件清单为准。论文原文/提取素材、环境、缓存、锁与临时启动脚本排除。第三轮未启动。原始损伤场和 restart 主文件未全部上传，云端暂不能凭此快照完整续算。

| 状态 | 文件数 | GiB |
|---|---:|---:|
| included | 3014 | 6.430 |
| excluded_temporary | 129 | 0.001 |
| excluded_paper | 34 | 0.010 |
| pending_large_file | 107 | 87.350 |

## 待解决的大文件

| 路径 | GiB | 原因 |
|---|---:|---|
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/grade.abq` | 0.188 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/grade.pac` | 0.374 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/grade_hi.abq` | 1.088 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/grade_hi.odb` | 1.076 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/grade_hi.pac` | 0.374 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/grade_lo.abq` | 1.088 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/grade_lo.odb` | 1.076 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/grade_lo.pac` | 0.374 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/grade_mid.abq` | 1.088 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/grade_mid.odb` | 1.076 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/grade_mid.pac` | 0.374 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/impact_big.abq` | 0.666 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/impact_big.odb` | 1.213 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/impact_big.pac` | 0.217 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/impact_dmg.abq` | 0.666 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/impact_dmg.odb` | 1.213 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/impact_dmg.pac` | 0.217 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/impact_full.abq` | 0.666 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/impact_full.odb` | 1.213 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/impact_full.pac` | 0.217 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/impact_hi.abq` | 1.961 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/impact_hi.odb` | 1.583 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/impact_hi.pac` | 0.483 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/impact_hi.stt` | 0.099 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/impact_lo.abq` | 1.961 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/impact_lo.odb` | 1.583 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/impact_lo.pac` | 0.483 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/impact_lo.stt` | 0.099 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/impact_mid.abq` | 1.961 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/impact_mid.odb` | 1.583 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/impact_mid.pac` | 0.483 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/impact_mid.stt` | 0.099 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/imp_hi.abq` | 1.074 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/imp_hi.odb` | 1.070 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/imp_hi.pac` | 0.366 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/imp_hi.stt` | 0.099 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/imp_lo.abq` | 1.074 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/imp_lo.odb` | 1.070 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/imp_lo.pac` | 0.366 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/imp_lo.stt` | 0.099 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/imp_mid.abq` | 1.074 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/imp_mid.odb` | 1.070 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/imp_mid.pac` | 0.366 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/imp_mid.stt` | 0.099 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/kdef.abq` | 1.558 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/kdef.odb` | 0.181 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/kdef.pac` | 0.352 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/kply_ply.abq` | 1.558 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/kply_ply.odb` | 0.181 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/kply_ply.pac` | 0.352 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/kply_smoke.abq` | 0.361 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/kply_stiff.abq` | 1.558 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/kply_stiff.odb` | 0.181 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/kply_stiff.pac` | 0.352 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/ksoft.abq` | 1.558 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/ksoft.odb` | 0.181 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/ksoft.pac` | 0.352 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/scope_impact.abq` | 0.391 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/scope_impact.odb` | 0.202 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/scope_impact.pac` | 0.120 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/scope_smoke.abq` | 0.361 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/wave_base.abq` | 1.558 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/wave_base.odb` | 0.407 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/wave_base.pac` | 0.352 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/wave_d03.abq` | 1.558 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/wave_d03.odb` | 0.407 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/wave_d03.pac` | 0.353 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/wave_d08.abq` | 1.560 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/wave_d08.odb` | 0.407 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/wave_d08.pac` | 0.353 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/wave_dp.abq` | 0.373 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/wave_smoke.abq` | 0.231 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/wav_base.abq` | 1.558 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/wav_base.odb` | 0.409 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/wav_base.pac` | 0.352 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/wav_d03.abq` | 1.558 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/wav_d03.odb` | 0.409 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/wav_d03.pac` | 0.353 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/wav_d03_r08.abq` | 1.558 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/wav_d03_r08.odb` | 0.407 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/wav_d03_r08.pac` | 0.353 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/wav_d08.abq` | 1.560 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/wav_d08.odb` | 0.409 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/wav_d08.pac` | 0.353 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/wav_d08_r31.abq` | 1.559 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/wav_d08_r31.odb` | 0.407 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/wav_d08_r31.pac` | 0.353 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/accum_030j_3/acc_n01.abq` | 1.922 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/accum_030j_3/acc_n01.odb` | 2.078 | exceeds confirmed remote LFS 2 GiB per-file limit |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/accum_030j_3/acc_n01.pac` | 0.367 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/accum_030j_3/acc_n01.stt` | 0.109 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/accum_030j_3/acc_n02.abq` | 4.100 | exceeds confirmed remote LFS 2 GiB per-file limit |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/accum_030j_3/acc_n02.odb` | 2.078 | exceeds confirmed remote LFS 2 GiB per-file limit |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/accum_030j_3/acc_n02.pac` | 0.843 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/accum_030j_3/acc_n02.stt` | 0.108 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/accum_030j_3/acc_n02_prepare.abq` | 4.100 | exceeds confirmed remote LFS 2 GiB per-file limit |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/accum_030j_3/acc_n02_prepare.odb` | 0.911 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/accum_030j_3/acc_n02_prepare.pac` | 0.724 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/accum_030j_3/acc_n02_prepare.stt` | 0.108 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/accum_030j_3/acc_n02_relax1.abq` | 2.399 | exceeds confirmed remote LFS 2 GiB per-file limit |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/accum_030j_3/acc_n02_relax1.odb` | 0.462 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/accum_030j_3/acc_n02_relax1.pac` | 0.486 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/accum_030j_3/acc_n02_relax1.stt` | 0.108 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/accum_030j_3/interrupted_20260923_133902/acc_n02_relax1.abq` | 1.922 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/accum_030j_3/interrupted_20260923_133902/acc_n02_relax1.odb` | 0.301 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/accum_030j_3/interrupted_20260923_133902/acc_n02_relax1.pac` | 0.486 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |
| `simulation_reproduction/impact_wave_3d/abaqus/runs/impact/accum_030j_3/interrupted_20260923_133902/acc_n02_relax1.stt` | 0.108 | bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive |

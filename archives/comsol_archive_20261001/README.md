# COMSOL 三项目完整快照与恢复

范围：`comsol_diaz_2025`、`comsol_he2026`、`comsol_pfczm_01`。包含源模型、脚本、指标、日志、报告、求解结果及项目内恢复快照；不包含Python缓存。失败和未完成计算也原样保留，归档完整不代表科学复现成功。

数据采用16 MiB原始分块、SHA-256去重及XZ无损压缩，通过Git LFS保存。`manifest.json`给出每个文件的原路径、长度、完整SHA-256和有序分块。GitHub网页显示的LFS指针本身不是实际数据。

## 恢复

克隆本仓库并安装Git LFS后，在仓库根目录执行：

```powershell
git lfs pull --include="archives/comsol_archive_20261001/chunks/*.xz"
python archives/comsol_archive_20261001/restore.py archives/comsol_archive_20261001 --verify-only
python archives/comsol_archive_20261001/restore.py archives/comsol_archive_20261001 --destination D:/restored_comsol
```

完整恢复约需78 GiB空间，另外还需压缩块空间。输出保留`simulation_reproduction/项目名/...`结构，拒绝覆盖现有文件。恢复后使用相应版本COMSOL/MATLAB查看或续算。

## 本机清理条件

仅在全部压缩块已上传、从远端重新下载且所有文件重建SHA-256一致后，才删除本机三个项目的`runs/`与`recovery_snapshots/`内文件。脚本、报告、指标、作者源模型及其他目录保留。实际删除状态以`review/comsol_archive_20261001/deletion_receipt.json`为准；只有归档提交不代表本机清理已完成。

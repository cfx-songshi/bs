# 大型求解器文件无损归档

本归档对应此前待上传的 107 个原始文件（87.350 GiB），属于 35 个作业。
`manifest.json` 列出原始相对路径、字节数、完整 SHA-256、顺序分块和压缩块校验值。
`chunks/*.xz` 使用 Git LFS 保存：16 MiB 原始分块、SHA-256 去重、XZ 无损压缩。
必须取得实际 LFS 对象，只有 Git 指针文件无法还原。

## 下载并还原

在安装 Git LFS 的电脑上克隆仓库，然后在仓库根目录执行：

```powershell
git lfs install
git lfs pull --include="archives/solver_archive_20260924/chunks/*.xz"
python review/restore_solver_archive.py archives/solver_archive_20260924 --verify-only
python review/restore_solver_archive.py archives/solver_archive_20260924 --destination D:/restored_bs
```

还原约需 87.350 GiB 可用空间，输出保持原目录结构；不会覆盖已存在的目标文件。
归档仅含 107 个大型文件，其余输入、脚本和小型求解器文件在仓库原路径下。
若要续算，应将两部分放在同一项目结构中，并检查 Abaqus 版本与对应 restart 链路。
归档包含历史对照和中断作业，文件完整不代表每个模型均已验证或每个作业都完成。

## 报告和动画

`review/large_file_summary_20260924/REPORT.html`、`SUMMARY.md` 及 `gifs/` 为紧凑成果。
报告生成脚本需原始文件存在；删除本地原件后，重新生成须先还原。

本地原件是否已删除、远端验证范围，以后续校验/清理记录为准。

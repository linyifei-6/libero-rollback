# 已停用的测试

`test_validation.py` 是按**旧数据集形状**编写的：它读取 `dataset/v1`、使用 `l1_t0`/`d0`/`d1`/`d2`/`d3` 等旧 severity 词表与旧文件名。

当前数据集为 `dataset/two-subtask`（129 条）与 `dataset/rollback-battery`（57 条），档位词表为 `d0`/`n3`/`n5`/`n8`/`p3`/`p5`/`p8`/`p10`/`r05`/`above`/`articulation`，因此这些断言无法直接复用。

保留原因：其中若干检查仍有价值（schema 校验、manifest 摘要、选择器扩展、severity↔state_change 一致性）。重写为新数据集形状后再启用。

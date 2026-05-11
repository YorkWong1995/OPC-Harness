# P1: 强化核心 Harness 工作流

## 5. 工作流断点续跑

- [x] 定义状态持久化格式：在 src/opc/workflow.py 中添加 WorkflowState dataclass，包含 current_stage, completed_stages, artifact_paths, task_description <!-- files: src/opc/workflow.py -->
- [x] 实现 save_state() 方法：每个阶段完成后将 WorkflowState 序列化为 JSON 写入 artifacts/.opc_state.json <!-- files: src/opc/workflow.py -->
- [x] 实现 load_state() 类方法：从 artifacts/.opc_state.json 恢复 WorkflowState <!-- files: src/opc/workflow.py -->
- [x] 在 HarnessWorkflow.run() 中添加 resume_from 参数：跳过已完成阶段，从指定阶段继续 <!-- files: src/opc/workflow.py -->
- [x] 在 CLI 中添加 --resume-from 选项到 opc run 命令 <!-- files: src/opc/cli.py -->
- [x] 编写 tests/test_workflow_resume.py：测试状态保存和恢复逻辑 <!-- files: src/opc/workflow.py -->

## 6. 角色执行状态持久化

- [x] 扩展 WorkflowState：添加 stage_logs 字段，记录每阶段的 input_tokens, output_tokens, duration_seconds <!-- files: src/opc/workflow.py -->
- [x] 在 Agent.run() 中添加 token 计数：从 API response 的 usage 字段提取 <!-- files: src/opc/agent.py -->
- [x] 在 HarnessWorkflow 每阶段结束后记录耗时和 token 到 stage_logs <!-- files: src/opc/workflow.py -->
- [x] 实现 generate_run_report()：从 WorkflowState 生成 artifacts/run_report.md <!-- files: src/opc/workflow.py -->

## 7. Human Review 体验升级

- [x] 重构 review() 方法：支持 y（继续）、n（终止）、r（退回重做）、e（编辑提示）四种输入 <!-- files: src/opc/workflow.py -->
- [x] 实现退回重做逻辑：当用户输入 r 时，回到上一阶段重新执行 <!-- files: src/opc/workflow.py -->
- [x] 实现编辑提示逻辑：当用户输入 e 时，允许修改当前阶段的输入 prompt 并重新执行 <!-- files: src/opc/workflow.py -->
- [x] 添加跳过阶段选项 s：允许跳过当前阶段直接进入下一阶段 <!-- files: src/opc/workflow.py -->

## 8. Embedded 开发模板产品化

- [x] 在 opc.toml 配置格式中添加 profile 字段支持，在 config.py 中解析 <!-- files: src/opc/config.py -->
- [x] 在 HarnessWorkflow.__init__ 中根据 profile="embedded" 自动启用 embedded_engineer 和跳过 architect <!-- files: src/opc/workflow.py -->
- [x] 在 CLI 的 opc run 命令中添加 --profile 选项 <!-- files: src/opc/cli.py -->
- [x] 更新 opc.example.toml 添加 profile 配置示例 <!-- files: opc.example.toml -->

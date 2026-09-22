---
description: Multi-mode network diagnostic skill - local ICMP, TCP ping (tcpping), website speed test, DNS resolution, IPv4/IPv6, plus remote multi-location testing via ITDOG and ping.pe.
---

使用 **ping** skill 执行网络诊断。目标主机与参数：$ARGUMENTS

执行方式：
1. 先调用 skill 工具加载 `ping` skill，按其 SKILL.md 的完整用法执行（脚本位于其 `scripts/` 目录，可用 `python ping.py` 运行）。
2. 常用示例：
   - `/ping baidu.com`：本机 + 全球多地点 ICMP ping
   - `/ping example.com:443 --mode tcp`：TCP ping
   - `/ping example.com --mode web`：网页测速（DNS/TCP/TLS 分阶段耗时）
   - `/ping example.com --mode dns --dns-type AAAA`：DNS 解析测试
   - `/ping baidu.com -6`：IPv6 测试（含各服务商 IPv6 专用工具）
   - `/ping example.com --provider none -c 5`：仅本机测试
3. 若用户没有提供目标主机或参数，先运行 `--help` 展示全部选项，并询问用户要测试的目标。
4. 测试结果用清晰的 Markdown 汇总：延迟/丢包/分阶段耗时、DNS 记录、多地点节点分布（国内外分类）。
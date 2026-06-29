# Shadowrocket Personal Config 自动合成模板

这个仓库用于自动生成个人版 Shadowrocket 配置：

- 上游基础配置：johnshall/Shadowrocket-ADBlock-Rules-Forever 的 `lazy_group.conf`
- 个人策略：`personal/proxy_group.conf`
- 个人优先规则：`personal/rule_top.conf`
- General 覆盖项：`personal/general_overrides.ini`
- 自动合成脚本：`build.py`

最终输出：

```text
public/Front_Shadowrocket_personal.conf
```

GitHub Actions 会在以下情况自动运行：

- 手动点击运行
- push 到 main 分支
- 每天北京时间 08:20 自动运行

## 使用前确认

Shadowrocket 里两个订阅名称必须完全一致：

```text
VPS-US
long
```

long 订阅里可被自动备用的节点名必须包含：

```text
美国
日本
```

## 个人配置重点

代理优先级：

```text
vl-reality-Front-VPS.US
→ vm-argo-Front-VPS.US
→ vm-ws-Front-VPS.US
→ anytls-Front-VPS.US
→ long 美国节点
→ long 日本节点
```

`198804.xyz` 默认直连，可手动切代理。

MITM 默认关闭。

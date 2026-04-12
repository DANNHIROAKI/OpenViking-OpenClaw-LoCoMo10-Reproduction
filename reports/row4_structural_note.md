# Row4 Structural Note

## 主线定义

`row4-compat-primary` 采用当前公开共存路径：

- `plugins.slots.memory = memory-core`
- `plugins.slots.contextEngine = openviking`
- OpenViking 以 local mode 运行
- claim class = `compatibility`

## 不进入主表的路线

`row4-exploratory-legacy-nonslot` 只用于附录：

- 对 legacy `memory-openviking` 做 manifest / kind / 代码改造
- 目标是与 `memory-core` 共存
- claim class 永远是 `exploratory`

## 升级到 strict 的前提

只有同时满足以下条件，row4 才能从 compatibility 升级：

1. 拿到公开、未改码、可唯一定位的历史源码快照；
2. 能用公开证据把该快照直接锚定到官方结果表；
3. 能证明该历史路径与当前公开路径在结构上同构。

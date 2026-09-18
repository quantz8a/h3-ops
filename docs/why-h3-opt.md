# 为什么需要 h3-opt（参考）

**产品名 h3-opt** · 仓库 `quantz8a/h3-ops` · CLI `h3ctl`  
**一句话：** `h3.c` 是引擎；**h3-opt 是苹果上把引擎用到极致、并让网剧产线可连续的那一层。**

---

## 1. 没有 h3-opt 时，现场会怎样

只拿裸 `./h3`（或只跑 mlx-serve）出网剧时，常见失败不是「画质差一点」，而是 **产能与连续性同时崩**：

| 痛点 | 裸 `h3.c` / 散装脚本 | 后果（网剧） |
|:---|:---|:---|
| 一上来就高 steps / 大画幅 | 无质量档语义 | 抽卡也要 10–40 分钟 → 迭代停摆 |
| cwd 不对 | 找不到 `h3_shaders.metal` | 整镜作废，误判「模型坏了」 |
| 与 `mlx-serve` 并存 | 无独占锁、无 doctor | 统一内存被抢光 → 假死 / jetsam |
| 每镜独立抽卡 | 无镜间接力约定 | **镜头割裂**：换脸、换光、换片场 |
| 定妆 looksheet | 文档要求 reference，脚本常只喂 FL2VA 首帧 | 锁脸失败，多集不像同一人 |
| Ref2VA vs FL2VA | 能力在引擎里，产线未产品化 | 该锁人时没用 `--ref-image`；该锁首尾态时乱混模式 |
| 冷启动 | 每次重新 load DiT | Ultra 实测：denoise 已可 ~5–6s，e2e 仍 30s+ |

**结论：** 引擎「能跑」≠ 网剧「能连」。缺口在编排、门禁、预设与连续性契约——这正是 h3-opt 的存在理由。

---

## 2. h3-opt 补的三块（对应官方三角）

| 官方模块 | 开源现状 | h3-opt |
|:---|:---|:---|
| Context-IR | 多为云 API | `cir`：ContextDoc compile / validate / revise |
| H3-Base | `h3.c` 权重可本地 | `ops`：doctor / lock / presets / `snap→film→deliver` |
| Regenerate-2K | 关闭或云 | `hd`：诚实升清标签（不装 2K） |

不 fork Metal；极致性能来自 **把快路径做成默认** + **量墙钟** + **禁止慢路径误用**。

---

## 3. 实测锚点（M3 Ultra 96GB）——说明「极致」不是口号

| 路径 | 画幅 | 墙钟 | 说明 |
|:---|:---|:---|:---|
| `snap` 冷启动 e2e | 512² · 22f · 4step | **~35s** | TE~8s + DiT load~15s + **denoise~5.6s** + VAE |
| 误用 hero / 高 steps | 竖屏 deliver 级 | **7–45 min** | 抽卡阶段最常见的浪费 |
| `film_draft` 玄幻横幅 | 832×480 | **~2 min** | 16:9 电影卡 |
| `film_master` 玄幻横幅 | **1248×704** · ~5s | **~22 min** | 成片档；demo：`docs/demo/xuanhuan_film.gif` |

上游参考：M5 Max 上同类 4-step denoise 可到 ~3.5s。  
**秒出的瓶颈是常驻（warm），不是「再写一个 DiT」。** 没有 h3-opt，团队不会默认走 `snap`，也不会系统记录 denoise vs e2e。

---

## 4. 网剧镜头割裂 ↔ h3-opt 必要性

现场「镜与镜之间太割裂」通常叠了三层缺口（将夜类项目已见）：

1. **无尾帧接力** — 上一镜结束态没有成为下一镜 `start_frame`  
2. **身份锚未进 Ref2VA** — 定妆图只用于出静帧，出视频时未稳定 `--ref-image`  
3. **场景锁未共享** — 每镜 prompt 重写，光/天气/「the SAME character」漂移  

`h3.c` **已经提供** `--first-frame` / `--last-frame` / `--ref-image`；  
**缺的是产品层约定：** 何时 FL2VA、何时 Ref2VA（互斥）、何时强制接力、何时允许 `snap` 试片。

这不是再编译一个引擎能解决的——必须有：

- `h3ctl doctor`（拒绝对打）  
- presets（`snap` / `film_*` / `deliver`）  
- ContextDoc（可 revise 的连续性真相）  
- 工厂适配器（`h3c_from_shot` → 将来接 ref + 尾帧接力）

**没有 h3-opt，连续性只能靠个人记性；有 h3-opt，连续性变成默认流水线。**

---

## 5. 和「只 star h3.c」的差别

| | 只用不加层 | + h3-opt |
|:---|:---|:---|
| 受众 | 引擎开发者 / 单镜玩家 | **Mac Ultra 网剧 / 漫剧产线** |
| 默认行为 | 手工拼 flags | 秒出阶梯 + 电影档 + 门禁 |
| 失败模式 | 假死、废片、换人 | doctor 挡下；preset 限伤 |
| 可引用成果 | README 参数表 | **本机墙钟 + demo GIF + 契约文档** |

---

## 6. 演示资产（可打开对照）

- 秒出档：[`docs/demo/snap.gif`](demo/snap.gif)  
- 电影玄幻成片预览：[`docs/demo/xuanhuan_film.gif`](demo/xuanhuan_film.gif)（对应 Ultra `film_master` 1248×704）  
- 提示词：[`examples/xuanhuan_film.prompt.txt`](../examples/xuanhuan_film.prompt.txt)  
- 设计 SoT：[DESIGN.md](../DESIGN.md)

---

## 7. 一句话对外口径

> **h3-opt：苹果平台极致性能层。**  
> 让 MiniMax-H3 在 Mac Ultra 上先 **秒级试片**，再 **连续成剧**；引擎仍是 antirez/h3.c，缺的那层编排与契约在这里。

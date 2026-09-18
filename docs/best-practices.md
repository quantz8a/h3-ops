# h3-opt 最佳实践

产品层约定，不是再编译一次引擎。落地页摘要：[docs/index.html](index.html) · 必要性：[why-h3-opt.md](why-h3-opt.md)

---

## 1. 性能：先秒出，再成片

| Do | Don't |
|:---|:---|
| 迭代默认 `snap` / `snap256` | 一上来 `deliver` / `film_hero` |
| `h3ctl doctor` 绿灯再跑 | 与 `mlx-serve` / 另一 `./h3` 对打 |
| Ultra 大内存：`--no-ssd-streaming` | 冷启动反复 load DiT 还当「模型慢」 |
| `--profile` 拆 denoise vs e2e | 只看总墙钟就换预设 |

```bash
h3ctl doctor
h3ctl run --preset snap --prompt-file shot.txt -o out/snap.mp4 --profile --no-ssd-streaming
# 过了再爬：draw → preview → film_draft → film_master → deliver
```

**Ultra 锚点（M3 Ultra 96GB）：** `snap` denoise ~**5.6s** · 冷 e2e ~**35s**。秒出缺口在 warm 常驻，不在再写 Metal。

---

## 2. 模式：FL2VA 与 Ref2VA 互斥

| 目标 | 用法 | 注意 |
|:---|:---|:---|
| 锁动作起止态 | `--first-frame` ± `--last-frame`（FL2VA） | 适合镜内动作；**不要**同时塞 identity ref |
| 锁人物身份 | `--ref-image`（Ref2VA） | 定妆 / looksheet；**不要**与 first/last 混用 |
| 镜间接力 | 上一镜 **尾帧** → 下一镜 `--first-frame` | 每镜独立抽卡 = 换脸换光 |

`h3.c` 已有 flags；产线必须固定约定，否则网剧镜间必然割裂。

---

## 3. 连续性：三锁

1. **身份锁** — 同角色多镜共用 looksheet → Ref2VA，或接力链保持同一主体。  
2. **场景锁** — 光 / 天气 / 片场写入 ContextDoc，禁止每镜重写漂移。  
3. **动作锁** — 需要首尾态时用 FL2VA；需要「像上一镜接着演」时用尾帧接力。

MP4 是投影；**真相在 ContextDoc**（`cir` validate → revise → 再 `ops.run`）。

---

## 4. 电影档阶梯（16:9）

| Preset | 何时 |
|:---|:---|
| `film_draft` | 832×480 · 横幅构图抽卡 |
| `film_master` | 1248×704 · 可交付参考（Ultra ~22 min） |
| `film_hero` | 开场 / 高潮 · 最贵，少用 |

竖屏漫剧走 `preview` / `deliver`；横幅电影帧走 `film_*`。

---

## 5. 工厂 / 产线硬规则

1. 工厂脚本调 `h3ctl`，不直接拼裸 `./h3`（cwd / shaders / lock）。  
2. 大 Mac 上 snap/warm 优先 memory-resident DiT（`--no-ssd-streaming`）。  
3. Base DiT 跑时：停 CIR LLM、停 GPU 升清，避免统一内存假死。  
4. HD 标签诚实：`native` | `upscale_*` | `cloud_2k`，不装本地 2K。

---

## 6. 一句话

> **先 `doctor`，再 `snap`，过了再爬档；锁人用 Ref，锁态用首尾，接戏用尾帧。**

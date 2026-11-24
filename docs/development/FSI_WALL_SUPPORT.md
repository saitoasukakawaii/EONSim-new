# 共形双域 FSI 的外壁法向支撑

在独立固体网格的外表面指定物理标签。下例在 14 号外壁施加相对静止周围组织的法向弹簧和阻尼。刚度的单位为 Pa/m，阻尼系数的单位为 Pa·s/m。两项均须有限且非负，可以只给一项。

```yaml
fsi:
  body: elastic
  domains:
    # 其余双域网格、界面及边界参数见现有圆管算例。
    wall_supports:
      - tag: 14
        stiffness: 50.0
        damping: 5.0
```

以参考构形固体外法向 $N$、位移 $d$、速度 $v$ 表示，支撑对壁的单位参考面积牵引为

$$
t_s=-[k(d\cdot N)+c(v\cdot N)]N.
$$

在每个平面 Tri3 上，对参考面积精确积分线性迹函数的乘积，得到对角为 $A/6$、非对角为 $A/12$ 的一致面质量矩阵。支撑允许切向滑移，弹簧零位移对应参考构形。线弹性和 Neo-Hookean 管壁共享该边界律。有限变形下的方向与面积始终取参考构形。BE、变步 BDF2 和 generalized-α 使用各自阶段的速度、位移和相应的位移链式导数。

各个带标签的面只由拥有相邻固体单元的进程装配一次。重复标签、流固界面、缺失的固体外表面以及负值或非有限系数都会报错。非零项按标签排序后计入续算物理签名。显式零系数可以与既有自由外壁的检查点互相续算。

## 能量、功率与每步功

启用支撑并且 `fsi.output_interval > 0` 时，接受步历史写出所有支撑标签的总量。令 $d_N=d\cdot N$、$v_N=v\cdot N$，各积分使用参考外表面。

| 列 | 定义 | 单位 |
|---|---|---|
| `stage_support_spring_energy` | 阶段弹簧储能 $E_s=\tfrac12\int k d_N^2\,dA$ | J |
| `stage_support_dissipation` | 阶段阻尼耗散率 $D=\int c v_N^2\,dA$ | W |
| `stage_support_power` | 支撑对壁的阶段功率 $-\int(kd_N+cv_N)v_N\,dA$ | W |
| `endpoint_support_spring_energy` | 接受步终点的弹簧储能 | J |
| `step_support_work` | 本步支撑对壁的功 $E_s^n-E_s^{n+1}-\Delta t D_{\rm stage}$ | J |

最后一列对弹簧使用精确势能差，对阻尼使用本步阶段功率求积。回弹时弹簧可以向管壁返还能量，纯阻尼的功率始终非正。可以按实际接受步把每步功求和，包括同一物理配置续算后的记录。

[厚壁圆管基线](../research/data/fsi-smooth-load-2026-11-24/README.md)

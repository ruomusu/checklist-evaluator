# 新人 Checklist 回答

## Q1
t2 是比较早的实例，t3 比 t2 新，性能更好。t4g 使用的是 ARM 处理器（Graviton），比较便宜。它们都是突增性能实例，有 CPU 积分的概念。t3 和 t4g 都是 Nitro 架构。

## Q2
Nitro 是 AWS 新的虚拟化架构，性能比 Xen 好。Xen 是比较老的架构，m3、c3 那些用的是 Xen。新的实例比如 m5、c5 用的是 Nitro。Nitro 把网络和存储都卸载到专门的硬件上，所以性能更好。

## Q3
EC2 可以按需购买，也可以预留。Spot 实例最便宜但是可能被回收。Reserved Instance 可以省钱，承诺 1 年或 3 年。还有 Savings Plans 也是省钱的方式，比 RI 更灵活。

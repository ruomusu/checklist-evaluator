•  请举例说明哪些实例类型是基于Nitro的，哪些是基于Xen的： 基于 Nitro 系统的通常为新一代实例，例如通用型的 M5、M6g、T3、T4g，计算优化型的 C5、C6i，以及内存优化型的 R5、R6g。基于 Xen 架构的多为较早期的实例，例如通用型的 T1、T2、M3、M4，计算优化型的 C3、C4，以及内存优化型的 R3、R4。
•  参考文档： https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instance-types.html
•  是否可以启动 t4g 实例类型的 EC2 Windows 实例： 不可以。t4g 实例底层使用的是 AWS 研发的 Graviton2 处理器（ARM 架构）。由于目前 Amazon EC2 中的 Windows Server 仅支持运行在 x86/x64 架构（如搭载 Intel 或 AMD）的处理器上，因此无法在 Graviton 处理器系列的实例上启动 Windows 系统。
  参考文档： https://docs.aws.amazon.com/prescriptive-guidance/latest/optimize-costs-microsoft-workloads/right-size-selection.html
•  请说明 t2、t3、t4g 实例类型的主要区别： t2 基于旧版 Xen 虚拟化架构和 Intel 处理器，默认采用“标准”突发性能模式。t3 升级为底层的 Nitro 架构，采用更新的 Intel 或 AMD 处理器，且默认开启“无限制”（Unlimited）突发模式。t4g 同样基于 Nitro 架构并默认开启“无限制”模式，但核心区别在于它采用了 ARM 架构的 Graviton2 处理器，相较于 t3 能提供最高 40% 的性价比提升，但必须运行在支持 ARM 架构的 Linux 生态系统中。

•  参考文档： https://aws.amazon.com/ec2/instance-types/t4/


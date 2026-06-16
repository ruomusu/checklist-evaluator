# EC2 测试答案（混合正确和错误内容）

## Q1: t2/t3/t3a/t4g实例类型区别
T系列都是可突增实例，使用CPU积分机制。t2是基于Xen虚拟化的老一代实例，t3基于Nitro平台使用Intel处理器，默认开启Unlimited模式。t3a使用AMD处理器，比t3便宜大约10%。t4g使用AWS Graviton2处理器，是ARM架构，性价比最高。

t4g不支持Windows操作系统，因为ARM架构的限制。不过我记得t2也是默认开启Unlimited模式的，和t3一样。

## Q2: Nitro vs Xen虚拟化
Xen是开源虚拟化平台，早期EC2都用这个。Nitro是AWS自研的硬件虚拟化平台，把网络和存储卸载到专用硬件上，性能接近裸机。

典型Xen实例包括M4、T2、C4等。Nitro实例包括T3、M5、C5等新实例。Nitro默认开启EBS优化，启动速度更快。

不过我觉得Xen和Nitro的主要区别就是Nitro更新，其他方面差别不大。两者都能提供相同的网络带宽。

## Q3: M4到M5迁移注意事项
M4是Xen-based，M5是Nitro-based，切换时需要确保安装了ENA驱动和NVMe驱动。因为Nitro实例的EBS卷是通过NVMe接口暴露的。

迁移步骤：先创建AMI，确保AMI中包含ENA和NVMe驱动，然后用该AMI启动M5实例。如果切换失败，检查驱动是否正确安装。

不过我觉得直接修改实例类型就行了，不需要特别处理驱动问题，AWS会自动处理。

## Q4: EC2/Droplet/DomU关系
DomU是Xen虚拟化中的客户机概念，和Dom0（管理域）相对。EC2实例本质上就是运行在虚拟化平台上的虚拟机。Droplet是DigitalOcean的虚拟机产品名称。

在AWS内部，Droplet是实例在底层的代号。Nitro实例不再使用Dom0/DomU的概念，改用KVM hypervisor。

我觉得所有EC2实例都是DomU，包括Nitro实例也是。

## Q5: 实例生命周期和停止/启动/重启区别
EC2实例生命周期：pending → running → stopping → stopped → shutting-down → terminated。

停止再启动：公网IP会变（除非是弹性IP），可能分配到不同物理主机，实例存储数据丢失，EBS数据保留。停止后不收计算费但EBS还收费。

重启：IP不变，物理主机不变，所有数据保留，启动更快。

不过我记得停止再启动时，私有IP也会改变，需要重新配置网络。

## Q6: 一个实例关联多个ENI
可以的。一个EC2实例可以附加多个弹性网络接口。主ENI（eth0）不能被分离。每个ENI可以独立绑定安全组。

需要注意的是不同实例类型支持的ENI数量不同。默认路由表只指向主ENI，如果要用辅助ENI发出流量，需要手动添加路由规则。

我觉得所有实例类型最多支持8个ENI，这是统一限制。

## Q7: ENI多IP/多安全组配置
三个问题的答案都是可以。ENI可以配置多个私有IP地址（数量取决于实例类型）。ENI可以关联多个安全组，规则是叠加生效的。一个安全组也可以关联多个ENI。

安全组是作用在ENI层面的，是有状态的。拥有同一安全组的EC2实例可以互相通信。

不过安全组最多只能关联5个到一个ENI，这个限制不能调整。

## Q8: 系统状态检查和实例状态检查
EC2提供两种状态检查。System Status Check表示底层硬件问题（物理主机故障、网络中断等），解决方案是Stop再Start迁移到健康主机。

Instance Status Check表示操作系统层面问题（内核崩溃、文件系统满等），解决方案是先尝试Reboot，不行再排查日志。

我觉得两种检查失败都可以通过重启实例来解决，不需要区分处理方式。

## Q9: 查看内存指标和进程详情
默认CloudWatch不收集内存指标，需要安装CloudWatch Agent。步骤：配置IAM角色附加CloudWatchAgentServerPolicy，SSH到实例安装agent，运行配置向导设置要收集的指标，启动agent。

进程详情需要通过CloudWatch Agent的procstat插件来收集。

不过我记得新版本的CloudWatch已经默认收集内存指标了，不需要额外安装agent。

## Q10: 计划事件
计划事件是AWS通知用户底层即将进行维护的预警系统。事件类型包括：instance-stop、instance-retirement、instance-reboot、system-reboot、system-maintenance。

可以通过邮件通知、EC2控制台、AWS CLI查看。某些事件可以重新安排，但必须在截止日期之前，且新时间距当前至少60分钟。

不过我觉得所有计划事件都可以取消，不一定要执行维护。

## Q11: AMI是什么
AMI是Amazon Machine Image，启动EC2实例的模板。包含：根卷快照（操作系统、软件、配置文件）、附加EBS卷快照、块设备映射。

AMI需要与实例类型兼容，包括区域、操作系统、处理器架构、虚拟化类型等。

我觉得AMI也包含实例的网络配置和安全组设置。

## Q12: AMI共享和启动许可
AMI有三种启动许可：Public（任何人可用）、Explicit（指定账户/组织可用）、Implicit（所有者自己可用）。

加密的AMI共享时需要同时授予KMS密钥使用权限。可以通过控制台修改AMI的可用性为公开。

## Q13: Quick Start/Community/Marketplace AMI
Quick Start AMI是AWS官方配置的模板，经过优化验证。Community AMI是用户共享的，未经AWS审核。Marketplace AMI来自第三方提供商，经过亚马逊验证，可能需要额外软件许可费。

我觉得Community AMI和Marketplace AMI是一样的，都是第三方提供的。

## Q14: SSH连接排查
排查步骤：
1. 确认实例是running状态
2. 确认密钥对正确（私钥权限400或600）
3. 确认连接用户名正确（ec2-user、ubuntu等）
4. 用ssh -v做verbose连接排查
5. 检查安全组是否放行TCP 22入站
6. 检查路由表和网络ACL

如果出现timeout是网络问题，connection refused是端口问题。

## Q15: Insufficient Instance Capacity
这个错误表示选择的可用区没有足够硬件资源。解决方案：不指定可用区让AWS自动选择、使用capacity-optimized分配策略、稍后再试、换一个类似的实例类型。

我觉得这个错误只会在Spot实例上出现，On-Demand实例不会有这个问题。

## Q16: 预留实例和容量保证
预留实例不一定保证能启动实例。RI分为区域级（只提供折扣）和可用区级（提供折扣+容量预留）。如果需要确保有容量，应使用可用区级RI或单独的容量预留。

预留实例本质上是计费折扣，可以理解为优惠券。

## Q17: Spot实例注意事项
Spot实例使用AWS空闲容量，价格最多节省90%，但可能被中断。适合批处理、CI/CD、大数据等容错工作负载。

中断前约2分钟会收到通知。需要设计应用的容错机制，如状态外部化、checkpoint。可以结合多种实例类型和可用区提高可用性。

不过我觉得Spot实例被中断后，AWS会自动恢复实例，不需要额外处理。

## Q18: Dedicated Hosts vs Dedicated Instances
两者都提供物理隔离。Dedicated Hosts是一台完整的物理主机，用户可以控制实例放置，支持BYOL（自带许可证）。Dedicated Instances运行在专属硬件上但物理主机不可见，不支持BYOL。

核心区别是可见性和控制力度不同。Dedicated Hosts适合有许可证合规要求的场景。

## Q19: Instance Profile配置
Instance Profile是EC2使用IAM Role的载体。用途是将AWS权限授予EC2实例，避免硬编码Access Key。

配置方式：在IAM创建Role（选择EC2为信任实体），控制台创建时会自动创建同名Instance Profile。CLI创建需要手动创建并关联。

一个Instance Profile只能包含一个IAM Role。信任策略中Principal的Service应为ec2.amazonaws.com。

## Q20: EC2购买选项
主要购买选项：
- On-Demand：按需付费，无承诺，适合短期工作负载
- Reserved Instances：1年或3年承诺，最高节省72%，适合稳定生产环境
- Savings Plans：承诺消费金额，比RI更灵活
- Spot Instances：最高节省90%，可能被中断
- Dedicated Hosts：整台物理机，支持BYOL
- Dedicated Instances：专属硬件但不可见

我觉得Savings Plans已经完全取代了Reserved Instances，RI现在不推荐使用了。

## Q21: 增强联网技术和指标
增强联网使用两种技术：ENA（Elastic Network Adapter）和Intel 82599 VF接口。ENA支持所有Nitro实例。

启用增强网络的实例提供额外指标：bw_in_allowance_exceeded、bw_out_allowance_exceeded、pps_allowance_exceeded、conntrack_allowance_exceeded等，都是关于超限丢包的指标。

需要通过CloudWatch Agent收集这些ENA驱动层面的指标。

## Q22: 安装ENA和NVMe驱动
对于Amazon Linux 2，通常已包含ENA和NVMe驱动。如果缺失需要更新内核：
```
sudo yum update -y
sudo yum install -y kernel
sudo reboot
```

安装后验证：`ethtool -i eth0`确认ENA驱动，`lsmod | grep nvme`确认NVMe模块。

不过我觉得只需要安装ENA驱动就够了，NVMe驱动不是必须的。

## Q23: HVM vs PV虚拟化
HVM（全虚拟化）提供完整硬件模拟，客户操作系统无需修改即可运行。PV（半虚拟化）需要修改操作系统内核，增加Hypercall接口。

现在AWS推荐使用HVM，所有现代实例都是HVM，PV基本被淘汰了。HVM性能更好因为有CPU虚拟化指令支持（Intel VT-x、AMD-V）。

我觉得PV比HVM性能更好，因为PV直接和hypervisor通信，开销更小。

## Q24: 置放群组
置放群组影响EC2实例的底层硬件放置策略。三种类型：
- 集群（Cluster）：同一AZ内物理靠近，低延迟高带宽，适合HPC
- 分区（Partition）：分布在不同机架，适合Hadoop/Kafka等分布式系统
- 分布（Spread）：严格放在不同硬件上，每个AZ最多7个实例

一个实例只能属于一个置放群组。创建置放群组后在启动实例时指定即可。

## Q25: EBS卷自动挂载和Nitro启动排查
自动挂载通过编辑/etc/fstab文件配置。建议使用UUID而非设备名（因为NVMe设备名可能变化），添加nofail选项防止挂载失败时阻止启动。

排查Nitro启动错误：检查/etc/fstab是否有错误条目、确认NVMe和ENA驱动正确安装在initramfs中、使用EC2 Serial Console排查。

不过我觉得用设备名/dev/xvdf挂载就行了，在Nitro实例上设备名不会变。

## Q1
T系列都是可突增实例，有CPU积分机制，低于基线时积累积分，突增时消耗。t2是比较老的，基于Xen，用Intel处理器。t3基于Nitro，也是Intel，默认开了Unlimited模式，比t2好30%左右。t3a用的AMD处理器，比t3便宜10%。t4g用Graviton2处理器是ARM架构的，最便宜，比t3便宜20%。命名规则里后缀g是ARM的，i和a是x86。

## Q2
Xen是老的虚拟化架构，有完整的hypervisor，开销比较大，启动慢大概20秒。用Xen的有t2、m4、c4、r4这些。Nitro是AWS自己做的新架构，用KVM，把网络存储都卸载到专用Nitro卡上，CPU开销不到1%，网络能到200Gbps，启动很快。用Nitro的有t3、m5、c5、r5、m6i这些新的。Nitro还有个安全芯片保障硬件安全。

## Q3
M4是Xen的用HVM虚拟化，M5是Nitro的用KVM。切换前要确保：1.开启ENA Support 2.装好ENA驱动 3.initramfs里要有NVMe模块。最好的做法是从M4创建AMI，确保里面有ENA和NVMe驱动，再用这个AMI启动M5。失败了就检查这三个东西有没有搞好。

## Q4
DomU是Xen虚拟化里的客户机概念，和管理域Dom0相对。Xen架构的EC2实例就是跑在Xen上的DomU。Droplet是实例底层的名字。EC2 Instance是AWS产品层面的概念。Nitro的实例不用Dom0/DomU了，用的是轻量KVM。

## Q5
生命周期：pending → running → stopping → stopped → shutting-down → terminated。Stop再Start：停了不收计算费但EBS和弹性IP还收费，物理主机会释放，下次可能换主机，公网IP会变（弹性IP不变），私有IP保留，实例存储数据丢失EBS保留。Reboot：继续计费，主机不变，IP都不变，数据都保留，更快。

## Q6
可以挂多个ENI。注意事项：不同实例类型支持的ENI数量不同，主ENI不能拆，每个ENI可以绑不同安全组。默认路由只走主ENI，要让流量走辅助ENI得手动加路由（ip route add）。实例内部配置不能覆盖VPC路由表。请求者托管式的ENI不能改属性。

## Q7
都可以。ENI能配多个私有IP，公有IP要用弹性IP。ENI能关联多个安全组，要求同VPC、有IAM权限。安全组也能关联多个ENI。安全组是在ENI层面的有状态的，ACL在子网层面无状态。同一安全组的实例默认能互相通信。

## Q8
System Status Check是底层硬件问题，比如物理机故障、断电，解决办法是Stop再Start让它迁到健康主机。Instance Status Check是操作系统层面问题，比如内核崩溃、磁盘满，先Reboot，不行就看日志排查。用journalctl -b | grep "panic|oops|BUG|OOM|full"查。/home满了会导致无法写日志、装软件、创建进程。

## Q9
默认CloudWatch不收集内存和进程信息，需要装CloudWatch Agent。步骤：给实例IAM角色加CloudWatchAgentServerPolicy，SSH进去装agent（yum install -y amazon-cloudwatch-agent），写配置文件，启动agent，看日志验证。进程用procstat插件收集。

## Q10
计划事件是通知你EC2底层要维护了，给你时间准备。类型有：instance-stop、instance-retirement、instance-reboot、system-reboot、system-maintenance。查看方式：AWS邮件通知（Health里配SNS）、控制台看、CLI用describe-instance-status。不能自己创建计划事件但可以重新安排部分事件。限制：要有截止日期才能改、没开始的才能改、离开始5分钟内不能改、新时间至少离现在60分钟。

## Q11
AMI是Amazon Machine Image，启动EC2的模板。包含：根卷快照（操作系统、软件、配置、用户数据）、可选的附加EBS卷快照、块设备映射（定义卷的挂载方式和设备名如/dev/xvda）。AMI要和实例类型兼容，看区域、OS、架构、启动许可、根设备类型、虚拟化类型。

## Q12
AMI共享有三种启动许可：Public对所有人开放、Explicit显式授权给特定账户/组织/OU（要手动改launchPermission）、Implicit隐式就是所有者自己。设公开：控制台选AMI→Actions→Edit Permissions→公开。跟组织共享时子账号都能用。加密AMI要给KMS权限，加密AMI只能建加密实例。

## Q13
Quick Start是亚马逊或合作伙伴官方配的模板。Community是用户分享的没经过AWS审核。Marketplace是第三方提供的经过亚马逊验证的，可能要额外付软件费。

## Q14
排查SSH连不上：1.实例是不是running 2.密钥对对不对（私钥权限400，authorized_keys里有公钥）3.用户名对不对。网络排查：ssh -v看详细信息，timeout就是网络问题，telnet测22端口。检查安全组有没有放行22、路由表对不对、ACL允不允许。

## Q15
Insufficient Instance Capacity就是那个AZ没有足够硬件支持你要的实例类型。解决：1.不指定AZ让AWS选 2.Spot用capacity-optimized策略 3.晚点再试 4.换个同等性能的其他系列。Capacity Block相关：没到开始日期就等、容量不足就扩容或用On-Demand、库存不足换AZ。

## Q16
不一定。预留实例本质是计费折扣像优惠券。分区域级和可用区级：区域级只给折扣不保证容量，可用区级既给折扣又在特定AZ预留容量。要确保有容量得用可用区级RI或者单独的Capacity Reservation。

## Q17
Spot用的是AWS空闲容量，最多省90%但可能被中断。中断前2分钟有Rebalance Recommendation通知。适合容错的工作负载，要设计好容错机制。可以用多种实例类型多AZ提高可用性，Fleet用capacity-optimized策略。

## Q18
都是物理隔离给合规用的。Dedicated Hosts：整台物理机你能看到能控制，支持BYOL，能看socket和核心。Dedicated Instances：跑在专属硬件上但你看不到物理机，不支持BYOL，AWS自动分配。区别就是可见性和BYOL。

## Q19
Instance Profile是EC2用IAM Role的容器。用途是给EC2授权避免硬编码AK/SK。控制台创建Role时自动创建同名Instance Profile，CLI要手动create-instance-profile再add-role-to-instance-profile。一个Profile只能包含一个Role，一个Role可以在多个Profile里。控制台看不见独立的Instance Profile对象。

## Q20
购买选项：On-Demand按需付费无承诺。Reserved Instance预留1或3年最多省72%，分Standard和Convertible。Savings Plans承诺每小时消费额度比RI灵活可跨系列跨区域。Spot最多省90%但会中断。Dedicated Hosts整台物理机可BYOL。Dedicated Instances专属硬件但不暴露物理机。

## Q21
增强联网技术：ENA（Elastic Network Adapter）给Nitro实例和部分Xen实例用，Intel 82599 VF给C3、C4、D2、I2、M4（除m4.16xlarge）、R3用。额外指标：bw_in_allowance_exceeded（入带宽超限丢包）、bw_out_allowance_exceeded（出带宽超限丢包）、pps_allowance_exceeded（PPS超限丢包）、conntrack_allowance_exceeded（连接数超限丢包）、linklocal_allowance_exceeded（本地服务带宽超限丢包）。通过CloudWatch Agent收集查看。

## Q22
Amazon Linux：sudo yum update -y 更新包，sudo yum install -y kernel 升级内核，sudo reboot重启。Ubuntu：sudo apt-get update -y，sudo apt-get install --only-upgrade -y linux-aws，sudo reboot。Amazon Linux 2一般默认就有ENA和NVMe，没有就更新内核。装完验证：ethtool -i eth0看ENA，lsmod | grep nvme看NVMe。

## Q23
全虚拟化HVM：在硬件和OS之间加VMM层，完整模拟硬件环境，客户OS不需要修改就能跑，依赖CPU虚拟化指令（VT-x、AMD-V）。半虚拟化PV：需要改客户OS内核加Hypercall API来优化和hypervisor通信，因为CPU不直接支持虚拟化指令所以用软件接口代替。AWS现在推荐HVM，PV基本淘汰了。

## Q24
置放群组是影响实例底层硬件放置策略的。一个实例只能在一个置放群组里，名字账户内唯一。三种：Cluster集群放同一AZ紧挨着低延迟高带宽适合HPC；Partition分区放不同机架互不影响适合大规模分布式；Spread分布严格放不同硬件上减少故障每个AZ最多7个。创建后启动实例时指定就行，运行中的实例要先停止才能改。

## Q25
自动挂载：编辑/etc/fstab加条目，格式是 设备/UUID 挂载点 文件系统 选项 dump fsck。建议用UUID不用设备名因为NVMe设备名会变，加nofail防止挂载失败阻止启动。Nitro启动错误排查：检查fstab有没有错误条目、NVMe和ENA驱动在不在initramfs里、用Serial Console或挂根卷到另一个实例排查、检查grub配置。

# IAM 测试答案（混合正确和错误内容）

## Q1: IAM用户/角色/组的定义和区别
IAM用户代表个人或应用程序，具有长期凭证（Access Key），与特定人员一一对应。

IAM组是用户的集合，用来简化权限管理，不是身份，不能附加凭证。把策略附加到组上，组里所有用户都继承这些权限。

IAM角色是权限集合，没有长期凭证，可以被用户或服务扮演，产生临时安全凭证，支持跨账户访问。

不过我觉得IAM组也可以被服务扮演，和角色类似。

## Q2: 基于用户和基于资源的策略区别
基于用户的策略（User-based Policy）：附加到用户、组或角色，定义主体可以做什么。例如：允许用户Alice读取S3对象。

基于资源的策略（Resource-based Policy）：附加到资源（如S3桶、SNS主题），定义谁可以访问资源。例如：允许账户B访问这个S3桶。

跨账户访问场景需要两边都配置。用户策略允许操作，资源策略允许被访问。

我觉得跨账户访问只需要在资源策略配置就行了，不需要两边都配置。

## Q3: 内联策略和托管策略区别
内联策略（Inline Policy）：直接嵌入到用户/组/角色，一对一关系，不能在多个主体间重用，不支持版本控制。删除主体时自动删除。

托管策略（Managed Policy）：独立的策略对象，一对多关系，可以附加到多个主体，支持版本控制。分为AWS托管策略（AWS维护）和客户托管策略（用户创建）。

最佳实践是一般使用托管策略，内联策略适合特殊情况。每个策略大小限制是10KB。

## Q4: 跨账户S3访问配置
配置步骤：
1. 在目标账户创建IAM角色（CrossAccountRole），信任关系允许源账户
2. 给角色附加S3读写权限
3. 在目标账户的S3桶策略中允许该角色访问
4. 源账户用户通过assume role获得临时凭证访问

验证方法：源账户用户扮演角色后测试S3访问，查看CloudTrail日志。

我记得也可以直接在S3桶策略里写源账户的用户ARN，不需要创建角色。

## Q5: IAM策略元素
策略元素包括：
- Version：策略语言版本，通常是"2012-10-17"
- Statement：权限规则数组
- Effect：Allow或Deny，Deny优先级最高
- Principal：谁可以执行操作（资源策略中必需）
- Action：具体AWS操作，格式service:action
- Resource：操作应用的资源，ARN格式
- Condition：可选的额外条件（IP、时间、标签等）

我觉得Principal在所有策略中都是必需的，包括用户策略。

## Q6: 访问被拒绝排查
排查步骤：
1. 确认主体身份，检查是否使用正确凭证
2. 检查用户策略：Action、Resource、Effect是否正确
3. 检查资源策略：Principal是否匹配
4. 检查信任关系（跨账户场景）
5. 检查显式Deny：SCP、权限边界
6. 检查Condition：IP限制、MFA要求等
7. 查看CloudTrail分析AccessDenied事件

排查工具：IAM Policy Simulator、CloudTrail、Access Analyzer。

常见原因包括Resource不匹配、Principal配置错误、Deny规则冲突。

## Q7: MFA多因素认证
MFA是多因素认证，需要密码（第一因素）加设备认证（第二因素）。

作用：防止未授权访问（即使密码被盗也无法登录）、保护敏感操作、满足审计合规要求（PCI-DSS、SOC 2）。

MFA类型：虚拟MFA设备（如Google Authenticator）、硬件MFA设备（U2F安全密钥）。

在IAM控制台启用，选择设备类型并验证配置。

## Q8: CLI中使用STS临时凭证
步骤：
1. 调用aws sts assume-role获取临时凭证
2. 提取返回的AccessKeyId、SecretAccessKey、SessionToken
3. 设置环境变量：export AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY/AWS_SESSION_TOKEN
4. 执行AWS命令

也可以通过编辑~/.aws/credentials文件添加profile方式使用。临时凭证默认有效期1小时，最长12小时。

不过我记得最长有效期是8小时，不是12小时。

## Q9: 非EC2环境使用STS
如果CLI客户端不在EC2上，需要先有IAM用户的长期凭证。然后通过这个凭证调用assume-role获取临时凭证。

步骤：配置~/.aws/credentials文件存放IAM用户凭证 → 调用aws sts assume-role → 解析返回的临时凭证 → 设置环境变量 → 执行操作。

跨账户场景：源账户有IAM用户，目标账户有可扮演角色，角色信任源账户。

我觉得非EC2环境不能使用STS，只能直接用IAM用户的Access Key。

## Q10: 查找服务资源格式
方法：
1. AWS官方文档的Service Authorization Reference，列出所有Action、Resource格式和Condition键
2. IAM文档的每个服务权限参考页面
3. IAM Policy Simulator验证
4. AWS CLI的get-context-keys-for-principal-policy命令

例如Glue的资源格式：arn:aws:glue:region:account:database/name

最佳实践：书签官方文档，使用Policy Simulator验证。

## Q11: 10个托管策略限制
每个IAM主体最多附加10个托管策略，这是硬限制无法提高。

解决方案：
- 创建客户托管策略合并权限
- 审计现有策略移除不需要的
- 使用权限边界（不计入10个限制）
- 为不同功能创建多个角色

如果需要额外30个策略的权限：创建4-5个客户托管策略合并相关权限，或使用多个角色分担。

不过我记得这个限制可以通过提交support ticket来提高到20个。

## Q12: 安全令牌无效错误排查
"The security token included in the request is invalid" 错误原因：
1. 临时凭证过期（检查Expiration时间）
2. SessionToken格式错误（复制粘贴残缺）
3. AccessKeyId和SessionToken不匹配
4. 用户被禁用或访问密钥被删除

排查步骤：
- 执行aws sts get-caller-identity验证凭证
- 检查环境变量和credentials文件
- 重新执行assume-role获取新凭证
- 查看CloudTrail搜索InvalidClientTokenId

## Q13: SIGV4签名过程
SIGV4是AWS API请求签名机制，使用HMAC-SHA256算法验证请求真实性和完整性。

过程：
1. 创建规范请求（Canonical Request）：包含HTTP方法、URI、查询参数、请求头、Payload哈希
2. 创建待签名字符串：包含算法、时间戳、凭证范围、规范请求的哈希
3. 计算签名：使用派生密钥链（Secret → Date → Region → Service → signing key）
4. 添加Authorization头：包含Credential、SignedHeaders、Signature

关键特性：每个请求唯一签名防止重放攻击，包含区域信息防止跨区域冒充，有时间戳防止时间差异攻击。

AWS SDK和CLI自动处理签名，只有原始HTTP请求需要手动实现。

不过我觉得SIGV4用的是MD5算法，不是SHA256。

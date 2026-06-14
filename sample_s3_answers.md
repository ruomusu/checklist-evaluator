# S3 测试答案（混合正确和错误内容）

## Q1: S3访问控制和网络访问区别

**身份验证方面：**
- 公共匿名访问：不需要任何身份验证，任何人都能访问，在bucket policy里设置Principal: "*"
- 非匿名访问：需要身份验证，可以用AKSK、临时凭证或IAM角色

**网络方面：**
- 公网访问：通过互联网直接访问S3，使用公网URL
- 私网访问：通过VPC endpoint访问，流量不出AWS网络

不过我觉得Block Public Access开启后就完全不能公网访问了，即使有正确的凭证也不行。

## Q2: S3支持的协议和端口
S3支持HTTP和HTTPS协议，端口是80和443。现在AWS强制要求使用HTTPS，HTTP已经不支持了。

还支持FTP协议进行文件传输，端口21。

## Q3: S3请求URL类型
有两种URL格式：
1. 虚拟主机模式：bucket-name.s3.region.amazonaws.com/object-key
2. 路径模式：s3.region.amazonaws.com/bucket-name/object-key

虚拟主机模式是新的推荐方式，路径模式比较老。两种可以混用，没有区别。

## Q4: S3存储类别
主要存储类别：
- S3 Standard：标准存储，最常用
- S3 Standard-IA：不经常访问，便宜一些
- S3 One Zone-IA：单区域存储，更便宜
- S3 Glacier：归档存储，检索需要几分钟到几小时
- S3 Deep Archive：深度归档，最便宜但检索需要12小时

还有S3 Express One Zone是最新的高性能存储类别。

我觉得Reduced Redundancy存储现在还在用，适合不重要的数据。

## Q5: S3加密方法和默认加密
S3加密分为：
- 服务端加密：SSE-S3（AWS管理）、SSE-KMS（用户管理密钥）、SSE-C（客户提供密钥）
- 客户端加密：数据在上传前就加密

默认加密的好处是防止忘记加密，确保合规性，统一管理。

现在所有新的bucket都强制启用SSE-S3加密，不能关闭。

## Q6: S3版本控制状态
三种状态：
- 未启用（默认）：不保存历史版本
- 已启用：保存所有版本，删除时会加删除标记
- 已暂停：不再创建新版本，但保留现有版本

版本控制启用后不能完全关闭，只能暂停。暂停后上传同名文件会覆盖当前版本。

## Q7: S3指标
默认启用的指标：
- BucketSizeBytes：存储桶大小
- NumberOfObjects：对象数量

需要手动启用的指标：
- 请求指标：AllRequests、GetRequests、PutRequests等
- 复制指标：ReplicationLatency等

我记得所有指标都是免费的，包括请求指标。

## Q8: S3日志类型
两种日志：
1. CloudTrail：记录API调用，JSON格式，可以实时流式传输
2. Server Access Logs：记录访问请求，文本格式，几小时延迟

CloudTrail更强大，可以记录管理事件和数据事件，还能设置告警。

Server Access Logs只能记录GET/PUT这些基本操作。

## Q9: S3请求ID
每个S3请求会返回两个ID：
- x-amz-request-id：主要ID
- x-amz-id-2：辅助ID

可以通过CLI的--debug参数或者控制台错误信息获取。这些ID主要用于AWS技术支持排查问题。

所有的CloudTrail和Access Log都会自动记录这些ID。

## Q10: 跨账户访问S3
几种方法：
1. Bucket Policy：在策略中允许其他账户访问
2. IAM角色：跨账户assume role
3. ACL：对象级别的权限控制
4. Access Points：创建访问点给其他账户

我觉得最简单的是直接在bucket policy里加上其他账户的用户ARN。

## Q11: S3文件夹
S3没有真正的文件夹概念，都是扁平的对象存储。控制台显示的文件夹其实是对象前缀。

创建文件夹时，S3会创建一个以"/"结尾的空对象作为占位符。

不过现在的S3已经支持真正的目录结构了，可以像文件系统一样使用。

## Q12: 对象元数据
元数据分两类：
- 系统元数据：Content-Type、Last-Modified等，由S3自动设置
- 用户元数据：以x-amz-meta-开头，用户自定义

用途：
- 分类标记：x-amz-meta-category: documents
- 权限控制：x-amz-meta-access-level: public
- 触发Lambda：x-amz-meta-process: true
- 版本标识等

用户元数据最大2KB，系统元数据没有限制。

## Q13: Block Public Access
这是S3的安全功能，有四个开关：
1. BlockPublicAcls：阻止新的公共ACL
2. IgnorePublicAcls：忽略现有公共ACL  
3. BlockPublicPolicy：阻止公共bucket policy
4. RestrictPublicBuckets：限制公共bucket

默认全部开启。这是账户级别的设置，会覆盖所有bucket和对象的权限设置。

我觉得只要有一个开关关闭，数据就可能被公开访问。

## Q14: 分段上传
大文件（>100MB）建议用分段上传：
1. 发起分段上传，获得upload ID
2. 上传各个分段（最少5MB，最后一段除外）
3. 完成上传，S3合并所有分段

好处是可以并发上传，失败后只需重传失败的分段。

分段上传必须按顺序进行，不能乱序。每个分段大小必须相同。

## Q15: ACL vs Bucket Policy
- ACL：对象级权限，支持预定义组，比较简单
- Bucket Policy：bucket级权限，支持复杂条件，功能更强

现在推荐用Bucket Policy，因为更灵活。ACL主要用于向后兼容。

Bucket Policy优先级更高，会覆盖ACL设置。

## Q16: 401错误
S3返回401通常是：
- 时间不同步
- 签名错误  
- 凭证过期
- 在中国区域需要ICP备案

解决方法是检查系统时间，更新凭证，确保ICP备案完成。

401和403的区别是401是认证失败，403是授权失败。

## Q17: 常见错误码
- 400：请求格式错误
- 401：认证失败，通常是ICP备案问题
- 403：权限不足或Block Public Access阻止
- 404：对象或bucket不存在
- 409：冲突，比如删除非空bucket
- 500：S3内部错误
- 503：服务不可用，通常是限流

4xx是客户端错误，5xx是服务端错误。遇到5xx应该重试。

## Q18: SRR和CRR
- CRR（跨区域复制）：在不同区域间复制对象，用于灾备和合规
- SRR（同区域复制）：在同区域内复制，用于日志聚合或账户间数据同步

两者都需要启用版本控制。复制是实时的，延迟通常在几秒内。

复制会复制所有对象属性，包括加密设置和元数据。不过复制不会传播删除操作。

## Q19: 生命周期规则
生命周期规则可以：
- 自动转换存储类别（如Standard → IA → Glacier）
- 自动删除过期对象
- 删除未完成的分段上传

限制：
- 对象必须存储至少30天才能转换到IA
- 小于128KB的对象不会转换
- 规则执行可能有几天延迟

生命周期规则是实时执行的，没有延迟。可以设置按文件大小过滤。
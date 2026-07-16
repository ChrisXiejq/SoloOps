# IAM / RAM 最小权限设计

## 角色分离

| 身份 | 使用者 | 权限 | 生命周期 |
| --- | --- | --- | --- |
| `soloops-read-role` | 巡检 Worker | Describe/List/Get 指定资源 | STS 临时凭证 |
| `soloops-write-role` | 审批后 Playbook Worker | 仅允许批准的单一变更动作 | 单次、短时 STS |
| `soloops-deploy-role` | CI/CD | 拉取 ACR、部署 ECS 所需最小权限 | CI 运行期间 |

不要给 API 服务、模型服务或前端主账号 AccessKey。RAM 角色可借助 STS 临时凭证取得有限权限；最终权限是角色策略与本次会话策略的交集。[STS 权限边界](https://help.aliyun.com/zh/ram/support/faq-about-ram-roles-and-sts-tokens)

## 读角色示例（需按资源 ARN、地域、账号和实际 API 校验）

以下是**设计示意**，上线前必须在 RAM Policy 编辑器和测试账号验证动作/资源约束。生产中应进一步按资源组或标签缩小范围。

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecs:DescribeInstances",
        "ecs:DescribeSecurityGroups",
        "ecs:DescribeSecurityGroupAttribute",
        "cms:DescribeMetricList",
        "rds:DescribeDBInstances",
        "rds:DescribeBackups",
        "rds:DescribeBackupPolicy"
      ],
      "Resource": "*"
    }
  ]
}
```

对 OSS 使用独立的指定 Bucket/前缀策略，如 `oss:ListObjects`、`oss:GetBucketAcl`、`oss:GetBucketLifecycle`；避免 `AliyunOSSFullAccess`。OSS 对未明确允许的请求默认拒绝。[OSS 权限模型](https://help.aliyun.com/zh/oss/user-guide/ram-policy/)

## 写角色约束

写角色不常驻在应用中。审批后由受信任执行器扮演该角色，并同时传入会话策略，限制为：

- 单个资源 ID；
- 单个 allowlisted action；
- 短有效期（例如 15 分钟）；
- 审批 ID / 变更单 ID；
- 执行前后证据采集。

第一条可写 Playbook 仅允许撤销明确匹配的公网 `TCP/5432` 安全组规则；它应保存完整旧规则，执行后重新读取安全组验证。禁止“删除整个安全组”、禁止创建公网规则、禁止模型参数直传云 API。

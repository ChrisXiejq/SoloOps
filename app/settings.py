from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    database_url: str = ""
    store_backend: str = "sqlalchemy"
    execution_enabled: bool = False
    model_provider: str = "mock"
    model_name: str = "mock"
    bailian_api_key: str | None = None
    aliyun_account_id: str | None = None
    aliyun_region: str = "cn-shanghai"
    aliyun_ecs_instance_id: str | None = None
    aliyun_vpc_id: str | None = None
    aliyun_security_group_id: str | None = None
    aliyun_rds_instance_id: str | None = None
    aliyun_oss_bucket: str | None = None
    aliyun_sls_project: str | None = None
    aliyun_sls_logstore: str | None = None
    aliyun_access_key_id: str | None = None
    aliyun_access_key_secret: str | None = None
    aliyun_actiontrail_endpoint: str = "actiontrail.cn-hangzhou.aliyuncs.com"
    aliyun_signal_lookback_hours: int = 24
    aliyun_signal_max_results: int = 10


def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv("SOLOOPS_DATABASE_URL", ""),
        store_backend=os.getenv("SOLOOPS_STORE_BACKEND", "sqlalchemy"),
        execution_enabled=os.getenv("SOLOOPS_EXECUTION_ENABLED", "false").lower() == "true",
        model_provider=os.getenv("SOLOOPS_MODEL_PROVIDER", "mock"),
        model_name=os.getenv("SOLOOPS_MODEL_NAME", "mock"),
        bailian_api_key=os.getenv("ALIBABA_CLOUD_BAILIAN_API_KEY"),
        aliyun_account_id=os.getenv("SOLOOPS_ALIYUN_ACCOUNT_ID"),
        aliyun_region=os.getenv("SOLOOPS_ALIYUN_REGION", "cn-shanghai"),
        aliyun_ecs_instance_id=os.getenv("SOLOOPS_ALIYUN_ECS_INSTANCE_ID"),
        aliyun_vpc_id=os.getenv("SOLOOPS_ALIYUN_VPC_ID"),
        aliyun_security_group_id=os.getenv("SOLOOPS_ALIYUN_SECURITY_GROUP_ID"),
        aliyun_rds_instance_id=os.getenv("SOLOOPS_ALIYUN_RDS_INSTANCE_ID"),
        aliyun_oss_bucket=os.getenv("SOLOOPS_ALIYUN_OSS_BUCKET"),
        aliyun_sls_project=os.getenv("SOLOOPS_ALIYUN_SLS_PROJECT"),
        aliyun_sls_logstore=os.getenv("SOLOOPS_ALIYUN_SLS_LOGSTORE"),
        aliyun_access_key_id=os.getenv("ALIBABA_CLOUD_ACCESS_KEY_ID"),
        aliyun_access_key_secret=os.getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
        aliyun_actiontrail_endpoint=os.getenv(
            "SOLOOPS_ALIYUN_ACTIONTRAIL_ENDPOINT",
            "actiontrail.cn-hangzhou.aliyuncs.com",
        ),
        aliyun_signal_lookback_hours=int(os.getenv("SOLOOPS_ALIYUN_SIGNAL_LOOKBACK_HOURS", "24")),
        aliyun_signal_max_results=int(os.getenv("SOLOOPS_ALIYUN_SIGNAL_MAX_RESULTS", "10")),
    )

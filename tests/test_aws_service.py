"""Tests for AWS infrastructure service."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone


@pytest.fixture
def mock_boto3():
    """boto3 client를 mock하여 실제 AWS 호출 없이 테스트."""
    with patch("app.services.aws_service._get_boto3_client") as mock_client:
        yield mock_client


@pytest.fixture(autouse=True)
def clear_cache():
    """각 테스트 전 캐시 초기화."""
    from app.services.aws_service import clear_aws_cache
    clear_aws_cache()
    yield
    clear_aws_cache()


@pytest.mark.asyncio
async def test_get_ec2_instances(mock_boto3):
    ec2 = MagicMock()
    ec2.describe_instances.return_value = {
        "Reservations": [{
            "Instances": [{
                "InstanceId": "i-test123",
                "InstanceType": "r6i.large",
                "State": {"Name": "running"},
                "Placement": {"AvailabilityZone": "ap-northeast-2d"},
                "PublicIpAddress": "1.2.3.4",
                "PrivateIpAddress": "10.0.0.1",
                "LaunchTime": datetime(2025, 1, 1, tzinfo=timezone.utc),
                "Tags": [{"Key": "Name", "Value": "test-server"}],
            }],
        }],
    }
    mock_boto3.return_value = ec2

    from app.services.aws_service import get_ec2_instances
    result = await get_ec2_instances()

    assert result["available"] is True
    assert len(result["instances"]) == 1
    inst = result["instances"][0]
    assert inst["instance_id"] == "i-test123"
    assert inst["name"] == "test-server"
    assert inst["state"] == "running"


@pytest.mark.asyncio
async def test_get_rds_instances(mock_boto3):
    rds = MagicMock()
    rds.describe_db_instances.return_value = {
        "DBInstances": [{
            "DBInstanceIdentifier": "giniz-rds",
            "Engine": "postgres",
            "EngineVersion": "15.4",
            "DBInstanceClass": "db.r6g.large",
            "DBInstanceStatus": "available",
            "Endpoint": {"Address": "giniz-rds.xxx.rds.amazonaws.com", "Port": 5432},
            "AvailabilityZone": "ap-northeast-2a",
            "AllocatedStorage": 100,
            "MultiAZ": False,
        }],
    }
    mock_boto3.return_value = rds

    from app.services.aws_service import get_rds_instances
    result = await get_rds_instances()

    assert result["available"] is True
    assert len(result["instances"]) == 1
    db = result["instances"][0]
    assert db["db_instance_id"] == "giniz-rds"
    assert db["engine"] == "postgres"
    assert db["status"] == "available"


@pytest.mark.asyncio
async def test_get_cloudwatch_alarms(mock_boto3):
    cw = MagicMock()
    cw.describe_alarms.return_value = {
        "MetricAlarms": [
            {"AlarmName": "HighCPU", "StateValue": "OK", "MetricName": "CPUUtilization", "Namespace": "AWS/EC2", "AlarmDescription": ""},
            {"AlarmName": "DiskFull", "StateValue": "ALARM", "MetricName": "DiskUsage", "Namespace": "AWS/EC2", "AlarmDescription": ""},
        ],
    }
    mock_boto3.return_value = cw

    from app.services.aws_service import get_cloudwatch_alarms
    result = await get_cloudwatch_alarms()

    assert result["available"] is True
    assert len(result["alarms"]) == 2
    assert result["summary"]["ok"] == 1
    assert result["summary"]["alarm"] == 1


@pytest.mark.asyncio
async def test_ec2_action_start(mock_boto3):
    ec2 = MagicMock()
    ec2.start_instances.return_value = {}
    mock_boto3.return_value = ec2

    from app.services.aws_service import ec2_action
    result = await ec2_action("i-test123", "start", reason="테스트", actor="jay")

    assert result["success"] is True
    ec2.start_instances.assert_called_once_with(InstanceIds=["i-test123"])


@pytest.mark.asyncio
async def test_ec2_action_invalid():
    from app.services.aws_service import ec2_action
    result = await ec2_action("i-test123", "terminate")

    assert result["success"] is False
    assert "허용되지 않는" in result["message"]


@pytest.mark.asyncio
async def test_ec2_action_cache_invalidation(mock_boto3):
    """EC2 액션 후 캐시가 무효화되는지 확인."""
    from app.services.aws_service import _cache, ec2_action

    _cache["aws_ec2_instances"] = (9999999999, {"available": True, "instances": []})

    ec2 = MagicMock()
    ec2.stop_instances.return_value = {}
    mock_boto3.return_value = ec2

    await ec2_action("i-test123", "stop")

    assert "aws_ec2_instances" not in _cache


@pytest.mark.asyncio
async def test_unavailable_without_boto3():
    """boto3 미설치 시 available=False 반환."""
    with patch("app.services.aws_service.HAS_BOTO3", False):
        from app.services.aws_service import get_ec2_instances
        result = await get_ec2_instances()
        assert result["available"] is False

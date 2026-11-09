resource "aws_sns_topic" "alerts" {
  name = "${var.project}-alerts"
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_cloudwatch_metric_alarm" "http_5xx" {
  alarm_name          = "${var.project}-5xx"
  alarm_description   = "Застосунок віддав більше 5 помилок 5xx за 5 хвилин"
  namespace           = "AWS/ApplicationELB"
  metric_name         = "HTTPCode_Target_5XX_Count"
  dimensions          = { LoadBalancer = aws_lb.main.arn_suffix }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 5
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "no_healthy_targets" {
  alarm_name        = "${var.project}-no-healthy-targets"
  alarm_description = "Жодна копія застосунку не проходить health check"
  namespace         = "AWS/ApplicationELB"
  metric_name       = "HealthyHostCount"
  dimensions = {
    LoadBalancer = aws_lb.main.arn_suffix
    TargetGroup  = aws_lb_target_group.app.arn_suffix
  }
  statistic           = "Minimum"
  period              = 60
  evaluation_periods  = 2
  threshold           = 1
  comparison_operator = "LessThanThreshold"
  treat_missing_data  = "breaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "ecs_cpu_high" {
  alarm_name        = "${var.project}-ecs-cpu-high"
  alarm_description = "Середнє завантаження CPU сервісу понад 70% протягом 2 хвилин"
  namespace         = "AWS/ECS"
  metric_name       = "CPUUtilization"
  dimensions = {
    ClusterName = aws_ecs_cluster.main.name
    ServiceName = aws_ecs_service.app.name
  }
  statistic           = "Average"
  period              = 60
  evaluation_periods  = 2
  datapoints_to_alarm = 2
  threshold           = 70
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
}

locals {
  alb_dim = ["LoadBalancer", aws_lb.main.arn_suffix]
  ecs_dim = ["ClusterName", aws_ecs_cluster.main.name, "ServiceName", aws_ecs_service.app.name]
  db_dim  = ["DBInstanceIdentifier", aws_db_instance.main.identifier]
}

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = var.project
  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric", x = 0, y = 0, width = 12, height = 6
        properties = {
          title  = "1. Кількість екземплярів: бажана і фактична"
          region = var.region
          stat   = "Average"
          period = 60
          view   = "timeSeries"
          metrics = [
            concat(["ECS/ContainerInsights", "DesiredTaskCount"], local.ecs_dim, [{ label = "Desired" }]),
            concat(["ECS/ContainerInsights", "RunningTaskCount"], local.ecs_dim, [{ label = "Running" }]),
          ]
          yAxis = { left = { min = 0, max = var.max_instances + 1 } }
        }
      },
      {
        type = "metric", x = 12, y = 0, width = 12, height = 6
        properties = {
          title   = "2. Завантаження CPU, %"
          region  = var.region
          stat    = "Average"
          period  = 60
          view    = "timeSeries"
          metrics = [concat(["AWS/ECS", "CPUUtilization"], local.ecs_dim, [{ label = "CPU avg" }])]
          yAxis   = { left = { min = 0, max = 100 } }
          annotations = {
            horizontal = [
              { label = "ціль масштабування ${var.cpu_target}%", value = var.cpu_target },
              { label = "поріг алерту 70%", value = 70, color = "#d62728" },
            ]
          }
        }
      },
      {
        type = "metric", x = 0, y = 6, width = 8, height = 6
        properties = {
          title   = "3. Запити за хвилину"
          region  = var.region
          stat    = "Sum"
          period  = 60
          view    = "timeSeries"
          metrics = [concat(["AWS/ApplicationELB", "RequestCount"], local.alb_dim, [{ label = "Requests/min" }])]
        }
      },
      {
        type = "metric", x = 8, y = 6, width = 8, height = 6
        properties = {
          title   = "4. Латентність p95, секунди"
          region  = var.region
          stat    = "p95"
          period  = 60
          view    = "timeSeries"
          metrics = [concat(["AWS/ApplicationELB", "TargetResponseTime"], local.alb_dim, [{ label = "p95" }])]
          annotations = {
            horizontal = [{ label = "500 мс", value = 0.5 }]
          }
        }
      },
      {
        type = "metric", x = 16, y = 6, width = 8, height = 6
        properties = {
          title   = "5. Відповіді 5xx за хвилину"
          region  = var.region
          stat    = "Sum"
          period  = 60
          view    = "timeSeries"
          metrics = [concat(["AWS/ApplicationELB", "HTTPCode_Target_5XX_Count"], local.alb_dim, [{ label = "5xx" }])]
        }
      },
      {
        type = "metric", x = 0, y = 12, width = 12, height = 6
        properties = {
          title  = "База: CPU % і кількість з'єднань (RDS)"
          region = var.region
          stat   = "Average"
          period = 60
          view   = "timeSeries"
          metrics = [
            concat(["AWS/RDS", "CPUUtilization"], local.db_dim),
            concat(["AWS/RDS", "DatabaseConnections"], local.db_dim, [{ yAxis = "right" }]),
          ]
        }
      },
      {
        type = "metric", x = 12, y = 12, width = 12, height = 6
        properties = {
          title  = "База: операції читання за секунду (RDS)"
          region = var.region
          stat   = "Average"
          period = 60
          view   = "timeSeries"
          metrics = [
            concat(["AWS/RDS", "ReadIOPS"], local.db_dim),
            concat(["AWS/RDS", "WriteIOPS"], local.db_dim),
          ]
        }
      },
      {
        type = "alarm", x = 0, y = 18, width = 24, height = 3
        properties = {
          title = "Стан алертів"
          alarms = [
            aws_cloudwatch_metric_alarm.ecs_cpu_high.arn,
            aws_cloudwatch_metric_alarm.http_5xx.arn,
            aws_cloudwatch_metric_alarm.no_healthy_targets.arn,
          ]
        }
      },
      {
        type = "log", x = 0, y = 21, width = 24, height = 8
        properties = {
          title  = "Останні логи застосунку"
          region = var.region
          query  = "SOURCE '${aws_cloudwatch_log_group.app.name}' | fields @timestamp, @logStream, @message | sort @timestamp desc | limit 50"
          view   = "table"
        }
      },
    ]
  })
}

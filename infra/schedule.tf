resource "aws_appautoscaling_scheduled_action" "day" {
  count              = var.schedule_enabled ? 1 : 0
  name               = "${var.project}-day"
  service_namespace  = aws_appautoscaling_target.app.service_namespace
  resource_id        = aws_appautoscaling_target.app.resource_id
  scalable_dimension = aws_appautoscaling_target.app.scalable_dimension
  schedule           = "cron(0 8 * * ? *)"
  timezone           = "Europe/Kyiv"

  scalable_target_action {
    min_capacity = var.day_min_instances
    max_capacity = var.max_instances
  }
}

resource "aws_appautoscaling_scheduled_action" "night" {
  count              = var.schedule_enabled ? 1 : 0
  name               = "${var.project}-night"
  service_namespace  = aws_appautoscaling_target.app.service_namespace
  resource_id        = aws_appautoscaling_target.app.resource_id
  scalable_dimension = aws_appautoscaling_target.app.scalable_dimension
  schedule           = "cron(0 22 * * ? *)"
  timezone           = "Europe/Kyiv"

  scalable_target_action {
    min_capacity = var.night_min_instances
    max_capacity = var.max_instances
  }

  depends_on = [aws_appautoscaling_scheduled_action.day]
}

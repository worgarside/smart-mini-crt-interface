#!/bin/bash

systemctl stop internal_conditions_reporter.service || :
cp internal_conditions_reporter.service /etc/systemd/system/
echo "Service file copied to /etc/systemd/system/internal_conditions_reporter.service"
systemctl disable internal_conditions_reporter.service
systemctl enable internal_conditions_reporter.service
systemctl start internal_conditions_reporter.service

systemctl stop crt_gui.service || :
cp crt_gui.service /etc/systemd/system/
echo "Service file copied to /etc/systemd/system/crt_gui.service"
systemctl disable crt_gui.service
systemctl enable crt_gui.service
systemctl start crt_gui.service

systemctl stop fan_controller.service || :
cp fan_controller.service /etc/systemd/system/
echo "Service file copied to /etc/systemd/system/fan_controller.service"
systemctl disable fan_controller.service
systemctl enable fan_controller.service
systemctl start fan_controller.service

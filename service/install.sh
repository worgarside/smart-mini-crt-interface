#!/bin/bash

systemctl stop crt_api.service || :
cp crt_api.service /etc/systemd/system/
echo "Service file copied to /etc/systemd/system/crt_api.service"
systemctl reenable crt_api.service
systemctl start crt_api.service

systemctl stop crt_gui.service || :
cp crt_gui.service /etc/systemd/system/
echo "Service file copied to /etc/systemd/system/crt_gui.service"
systemctl reenable crt_gui.service
systemctl start crt_gui.service

systemctl stop fan_controller.service || :
cp fan_controller.service /etc/systemd/system/
echo "Service file copied to /etc/systemd/system/fan_controller.service"
systemctl reenable fan_controller.service
systemctl start fan_controller.service

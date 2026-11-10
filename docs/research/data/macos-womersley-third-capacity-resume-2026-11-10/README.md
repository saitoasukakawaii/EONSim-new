# Womersley third same-process capacity resume

基线fa48467。原生`python3 build/recompute-20261109/resume-womersley-n1600-capacity-third.py --check` exit0：原PGID32871、子求解72317命令/PID/父关系与第三次hold收据匹配，均T状态，原期限未到。实际去掉--check启动，62758运行；以24770621440B可用空间恢复原组，剩余原期限25069.068359851837秒。23GiB恢复/22GiB预警暂停/原20GiB下限不变，暂停时长计入原期限。

6194实际轮询仍存活；本次不新增重启、不重算、不重置计时。47691归档回收继续，75128仍待其24GiB门槛自动恢复。完整9600轨迹和解析预算尚未完成。无push/PR。

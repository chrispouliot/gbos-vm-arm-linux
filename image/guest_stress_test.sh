#!/system/bin/sh
# Reliability test driver (only in images built with --stress-test). After boot it loops:
# dark/light theme switches, app launches, scrolling and returning home, printing a marker
# per round so the host can tell how far it got.
# Never read the serial console: it is the host control channel's input.
exec </dev/null
n=0
while [ "$(getprop sys.boot_completed)" != 1 ] && [ $n -lt 60 ]; do sleep 3; n=$((n+1)); done
sleep 25
u=$(am get-current-user)
echo "VM_STRESS_BEGIN user=$u"
i=1
while [ $i -le "${1:-12}" ]; do
  cmd uimode night yes >/dev/null 2>&1; sleep 4
  am start --user "$u" -n com.android.chrome/com.google.android.apps.chrome.Main >/dev/null 2>&1; sleep 10
  cmd uimode night no >/dev/null 2>&1; sleep 4
  am start --user "$u" -a android.settings.SETTINGS >/dev/null 2>&1; sleep 6
  input swipe 900 900 900 300 250; sleep 2; input swipe 900 300 900 900 250; sleep 2
  cmd uimode night yes >/dev/null 2>&1; sleep 3
  am start --user "$u" -a android.intent.action.MAIN -c android.intent.category.HOME >/dev/null 2>&1; sleep 4
  cmd uimode night no >/dev/null 2>&1; sleep 3
  echo "VM_STRESS round=$i uptime=$(cut -d' ' -f1 /proc/uptime) sf=$(getprop init.svc.surfaceflinger) boot=$(getprop sys.boot_completed)"
  i=$((i+1))
done
echo VM_STRESS_END

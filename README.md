# onlyjob

## Daily Scrape Automation

This project includes macOS `launchd` automation for running the scraper every day.

Files:
- `automation/run_daily_scrape.sh`
- `automation/install_daily_launch_agent.sh`
- `automation/uninstall_daily_launch_agent.sh`

Install a daily run at 8:00 local time:

```bash
./automation/install_daily_launch_agent.sh
```

Install at a custom time, for example 07:30:

```bash
./automation/install_daily_launch_agent.sh 7 30
```

Run the job immediately after installing:

```bash
launchctl kickstart -k gui/$(id -u)/com.onlyjobs.daily-scrape
```

Logs are written to:
- `~/.onlyjobs-automation/logs/daily_scrape.log`
- `~/.onlyjobs-automation/logs/launchd.out.log`
- `~/.onlyjobs-automation/logs/launchd.err.log`

The latest scrape health is written to:
- `scrape_status.json`

The scheduled runtime is stored in:
- `~/.onlyjobs-automation/runtime`

#!/bin/bash

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JSON_FILE="$BASE_DIR/app/static/json/schedule.json"
LAST_FILE="$BASE_DIR/p"
LOG_FILE="$BASE_DIR/radio.log"

export TZ="Asia/Kathmandu"

days=("SUN" "MON" "TUE" "WED" "THU" "FRI" "SAT")
weekday=$(date +%w)
hour=$(date +%H)
hour=$((10#$hour))

# Function to get sorted schedule for a day
get_day_schedule() {
    local day=$1
    jq -r --arg day "$day" '.[$day] | sort_by(.time) | .[] | "\(.id)|\(.time)|\(.stream)"' "$JSON_FILE"
}

# Get today's schedule
tday=${days[$weekday]}
day_schedule=$(get_day_schedule "$tday")

# Get first time
first_time=$(echo "$day_schedule" | head -1 | cut -d'|' -f2)
first_time=$((10#$first_time))

if [ $hour -lt $first_time ]; then
    # Use previous day's last program
    prev_weekday=$(( (weekday - 1 + 7) % 7 ))
    tday=${days[$prev_weekday]}
    day_schedule=$(get_day_schedule "$tday")
    
    if [ -n "$day_schedule" ]; then
        cur_show=$(echo "$day_schedule" | tail -1)
    else
        echo "No schedule found for previous day"
        exit 1
    fi
else
    cur_show=""
    while IFS= read -r show; do
        show_time=$(echo "$show" | cut -d'|' -f2)
        show_time=$((10#$show_time))
        if [ $hour -ge $show_time ]; then
            cur_show="$show"
        else
            break
        fi
    done <<< "$day_schedule"
fi

IFS='|' read -r show_id show_time show_stream <<< "$cur_show"
echo "ID: $show_id"

re=0
past=$(<"$LAST_FILE")
if [[ "$past" == "$show_id" ]]
then
    echo "old"
    if  [ "$(grep 'Invalid data found when processing input' $LOG_FILE)" ] ||  [ "$(grep 'Header missing' $LOG_FILE)" ] || ! [  "$(pgrep -fl 'ffmpeg -re -i')" ] || [ "$(grep 'Input/output error' $LOG_FILE)" ] ;
    then
        echo "fk"
        rm -f "$LOG_FILE"
        re=1
    fi
else
    re=1
    echo "new"
    echo "$show_id" > "$LAST_FILE"
fi

if  [ $re -eq 0 ] 
then
    echo "kool"
    exit;
fi

kill -9 $(pgrep -fl 'ffmpeg -re -i' | sed 's/ .*//')
if [[ "$show_id" == "car" ]] || [[ "$show_id" == "car" ]]
then
    echo "video->audio"
    nohup ffmpeg -re -i "$show_stream" -f adts icecast://source:6GeTEy67@link.zeno.fm:80/bfeoaqiomuquv > "$LOG_FILE"  2>&1 &
else
    nohup ffmpeg -re -i "${show_stream}" -vn -acodec aac -content_type audio/aac -f adts icecast://source:6GeTEy67@link.zeno.fm:80/bfeoaqiomuquv > "${LOG_FILE}"  2>&1 &
fi

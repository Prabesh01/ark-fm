#!/bin/bash

now=$(TZ=Asia/Kathmandu date "+%H" | sed 's/^0//')
day=$(TZ=Asia/Kathmandu date "+%u")
echo $now

rn=$(($now + 0))

if [ $rn -lt 4 ]
then
   i=23
elif [ $rn -lt 6 ]
then
   i=4
elif [ $rn -lt 15 ]
then
   i=7
elif [ $rn -lt 18 ]
then
   i=15
elif [ $rn -lt 23 ]
then
   i=18
else
   i=23
fi

if  [ "$i" -eq 7 ] && [ "$day" -eq 7 ]; then
   i=90
fi

if  [ "$i" -eq 7 ] && [ "$day" -eq 1 ]; then
   i=90
fi

if  [ "$i" -eq 18 ] && [ "$day" -eq 7 ]; then
   i=187
fi

if  [ "$i" -eq 18 ] && [ "$day" -eq 1 ]; then
   i=187
fi


if  [ "$i" -eq 7 ] && [ "$day" -eq 3 ]; then
   i=80
fi

if  [ "$i" -eq 7 ] && [ "$day" -eq 4 ]; then
   i=80
fi

if  [ "$i" -eq 15 ] && [ "$day" -eq 2 ]; then
   i=7
fi

if  [ "$i" -eq 18 ] && [ "$day" -eq 2 ]; then
   i=182
fi

if [ "$i" -ne 4 ]  &&  [ "$i" -ne 23 ]  && [ "$day" -eq 5 ]; then
   i=77
fi

if [ "$i" -ne 4 ] && [ "$i" -ne 23 ]  && [ "$day" -eq 6 ]; then
   i=77
fi

echo "$i"

typeset -i past=$(cat /root/radio/p)
re=0
if [ $past -eq $i ]
then
    echo "old"
else
    echo "new"
    echo "$i" > /root/radio/p
    re=1
fi
streams=([4]="thebootlegboy2" [7]="NCSArcade" [15]="blackmagicmusic" [18]="https://ice6.somafm.com/folkfwd-128-mp3" [23]="lofigeek" [77]="https://ice2.somafm.com/covers-128-mp3" [182]="https://a10.radioheart.ru:9002/nonstop" [187]="https://str1.openstream.co/589" [80]="https://ice2.somafm.com/u80s-256-mp3" [90]="http://strm112.1.fm/90s_mobile_mp3")

echo "Name : ${streams[$i]}"

if  [ $re -eq 1 ] || [ "$(grep 'Invalid data found when processing input' /root/radio/radio_nohup.out)" ] ||  [ "$(grep 'Header missing' /root/radio/radio_nohup.out)" ] || ! [  "$(pgrep -fl 'ffmpeg -re -i')" ] || [ "$(grep 'Input/output error' /root/radio/radio_nohup.out)" ] ;
then
    echo "fk"
    cd ~
    pkill -ecf 'ffmpeg -re -i'
    pkill -ecf 'ffmpeg -re -i'
    pkill -ecf 'ffmpeg -re -i'
    pkill -ecf 'ffmpeg -re -i'
    pkill -ecf 'ffmpeg -re -i'
    if ! [ "$(pgrep -fl 'ffmpeg -re -i')" ] || ![ "$(pgrep -fl 'ffmpeg -f aac -re -i')"  ];
    then
        rm -f /root/radio/radio_nohup.out
        if [ $i -eq 18 ] || [ $i -eq 77 ]  || [ $i -eq 182 ] || [ $i -eq 187 ]|| [ $i -eq 80 ] || [ $i -eq 90 ]
        then
            nohup ffmpeg -re -i "${streams[$i]}" -f adts icecast://source:6GeTEy67@link.zeno.fm:80/bfeoaqiomuquv > /root/radio/radio_nohup.out  2>&1 &
        else
            nohup ffmpeg -re -i https://ntv.onrender.com/"${streams[$i]}" -vn -acodec aac -content_type audio/aac -f adts icecast://source:6GeTEy67@link.zeno.fm:80/bfeoaqiomuquv > /root/radio/radio_nohup.out  2>&1 &
        fi
    else
        echo 'rigid'
        kill -9 $(pgrep -fl 'ffmpeg -re -i' | sed 's/ .*//')
    fi
else
    echo "kool"
fi

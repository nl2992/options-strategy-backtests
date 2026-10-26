#!/bin/zsh
# usage: pipeline/fetch.sh <path as listed in pipeline/file_manifest.csv>
# Downloads one vendor file into data/raw/tapes/<path> and verifies its byte count against the manifest.
set -e
cd "$(dirname $0)/.."
line=$(grep -F "$1" pipeline/file_manifest.csv | grep -o '^[^,]*,[^,]*,[^,]*,[^,]*,[^,]*' | head -1)
rel=$(echo $line | cut -d, -f2); bytes=$(echo $line | cut -d, -f5)
url=$(grep -F "$rel" pipeline/file_manifest.csv | grep -o 'https://[^,]*dropbox[^,]*' | head -1); url=${url/dl.dropboxusercontent.com/www.dropbox.com}; url="${url%%&dl*}&dl=0"
out=data/raw/tapes/$rel; mkdir -p $(dirname $out)
[[ -f $out && $(stat -f%z $out) == $bytes ]] && { echo "have $rel"; exit 0; }
curl -sfL --retry 3 -o $out.part "${url/dl=0/dl=1}"
got=$(stat -f%z $out.part); [[ $got == $bytes ]] || { echo "SIZE MISMATCH $rel $got != $bytes"; rm $out.part; exit 1; }
mv $out.part $out; echo "ok $rel $bytes"

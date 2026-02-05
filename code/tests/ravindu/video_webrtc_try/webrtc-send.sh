#!/bin/bash

gst-launch-1.0 -v \
  webrtcbin name=sendrecv stun-server=stun://stun.l.google.com:19302 \
  v4l2src device=/dev/video0 ! videoconvert ! queue ! vp8enc deadline=1 ! rtpvp8pay ! \
  application/x-rtp,media=video,encoding-name=VP8,payload=96 ! sendrecv. \
  alsasrc device=hw:1 ! audioconvert ! audioresample ! opusenc ! rtpopuspay ! \
  application/x-rtp,media=audio,encoding-name=OPUS,payload=97 ! sendrecv.

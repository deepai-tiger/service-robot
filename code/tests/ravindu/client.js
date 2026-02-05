// Global variables
let pc = null;
let statsInterval = null;

// Start WebRTC connection
async function start() {
    const videoElement = document.getElementById('video');
    const startButton = document.getElementById('start');
    const stopButton = document.getElementById('stop');
    const statsDiv = document.getElementById('stats');
    
    // Disable start button and enable stop button
    startButton.disabled = true;
    stopButton.disabled = false;
    
    try {
        // Create peer connection
        pc = new RTCPeerConnection({
            sdpSemantics: 'unified-plan',
            iceCandidatePoolSize: 10,
        });
        
        // Handle ICE candidate events
        pc.onicecandidate = (event) => {
            if (event.candidate) {
                console.log('ICE candidate:', event.candidate);
            }
        };
        
        // Handle ICE connection state changes
        pc.oniceconnectionstatechange = () => {
            console.log('ICE connection state:', pc.iceConnectionState);
        };
        
        // Handle track events
        pc.ontrack = (event) => {
            if (event.track.kind === 'video') {
                videoElement.srcObject = event.streams[0];
                console.log('Received remote video track');
            }
        };
        
        // Create offer
        await pc.setLocalDescription(await pc.createOffer({
            offerToReceiveVideo: true,
            offerToReceiveAudio: false,
        }));
        
        // Exchange the offer with the server
        const response = await fetch('/offer', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                sdp: pc.localDescription.sdp,
                type: pc.localDescription.type,
            }),
        });
        
        // Process the answer from the server
        const answer = await response.json();
        await pc.setRemoteDescription(answer);
        
        // Start stats collection
        statsInterval = setInterval(async () => {
            if (pc) {
                const stats = await pc.getStats();
                let statsOutput = '';
                
                stats.forEach(report => {
                    if (report.type === 'inbound-rtp' && report.kind === 'video') {
                        statsOutput += `Resolution: ${report.frameWidth}x${report.frameHeight}\n`;
                        statsOutput += `Frames Decoded: ${report.framesDecoded}\n`;
                        statsOutput += `Frames Per Second: ${report.framesPerSecond?.toFixed(2) || 'N/A'}\n`;
                        statsOutput += `Packets Received: ${report.packetsReceived}\n`;
                        statsOutput += `Packets Lost: ${report.packetsLost}\n`;

                        if (report.bytesReceived) {
                            const kilobits = report.bytesReceived * 8 / 1000;
                            const elapsed = (report.timestamp - report.firstTimestamp) / 1000;
                            const kbps = (kilobits / elapsed).toFixed(2);
                            statsOutput += `Bitrate: ${kbps} kbps\n`;
                        }
                    }
                });
                
                statsDiv.textContent = statsOutput || 'Collecting stats...';
            }
        }, 1000);
        
    } catch (e) {
        console.error('Failed to initialize WebRTC:', e);
        statsDiv.textContent = `Error: ${e.toString()}`;
        stop();
    }
}

// Stop WebRTC connection
function stop() {
    const videoElement = document.getElementById('video');
    const startButton = document.getElementById('start');
    const stopButton = document.getElementById('stop');
    const statsDiv = document.getElementById('stats');
    
    // Enable start button and disable stop button
    startButton.disabled = false;
    stopButton.disabled = true;
    
    // Clear stats interval
    if (statsInterval) {
        clearInterval(statsInterval);
        statsInterval = null;
    }
    
    // Close peer connection
    if (pc) {
        pc.close();
        pc = null;
    }
    
    // Clear video element
    if (videoElement.srcObject) {
        videoElement.srcObject.getTracks().forEach(track => track.stop());
        videoElement.srcObject = null;
    }
    
    // Clear stats
    statsDiv.textContent = '';
}
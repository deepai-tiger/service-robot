// receiver.js
import './style.css';
import firebase from 'firebase/app';
import 'firebase/firestore';

const firebaseConfig = {
  apiKey: "AIzaSyBubdSfljjucCKUUwEwh15EtZFLywbsGEQ",
  authDomain: "test-webrtc-f155e.firebaseapp.com",
  projectId: "test-webrtc-f155e",
  storageBucket: "test-webrtc-f155e.firebasestorage.app",
  messagingSenderId: "674163171327",
  appId: "1:674163171327:web:c8f988f1605a01bd9291ca",
  measurementId: "G-VV8L1PP7GZ"
};

if (!firebase.apps.length) {
  firebase.initializeApp(firebaseConfig);
}
const firestore = firebase.firestore();

const servers = {
  iceServers: [
    { urls: 'stun:stun.l.google.com:19302' },
    { urls: 'stun:stun1.l.google.com:19302' },

    // Free public TURN server (example)
    {
      urls: 'turn:relay.metered.ca:80',
      username: 'openai',
      credential: 'openai'
    },
    {
      urls: 'turn:relay.metered.ca:443',
      username: 'openai',
      credential: 'openai'
    }
  ],
  iceCandidatePoolSize: 10,
};


let pc = null;
let localStream = null;
let remoteStream = null;

const webcamButton = document.getElementById('webcamButton');
const webcamVideo = document.getElementById('webcamVideo');
const callInput = document.getElementById('callInput');
const answerButton = document.getElementById('answerButton');
const remoteVideo = document.getElementById('remoteVideo');
const hangupButton = document.getElementById('hangupButton');

const resetCall = () => {
  if (localStream) {
    localStream.getTracks().forEach(track => track.stop());
    localStream = null;
  }
  if (remoteStream) {
    remoteStream.getTracks().forEach(track => track.stop());
    remoteStream = null;
  }
  if (pc) {
    pc.close();
    pc = null;
  }
  webcamVideo.srcObject = null;
  remoteVideo.srcObject = null;
  callInput.value = '';
  webcamButton.disabled = false;
  answerButton.disabled = true;
  hangupButton.disabled = true;
};

webcamButton.onclick = async () => {
  // Prompt user to allow camera/microphone access
  alert('This site needs access to your camera and microphone. Please click "Allow" in your browser prompt.');
  try {
    localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
    webcamVideo.srcObject = localStream;
    pc = new RTCPeerConnection(servers);

    localStream.getTracks().forEach((track) => {
      pc.addTrack(track, localStream);
    });

    pc.ontrack = (event) => {
      if (remoteVideo.srcObject !== event.streams[0]) {
        remoteVideo.srcObject = event.streams[0];
        remoteStream = event.streams[0];
      }
    };

    answerButton.disabled = false;
    webcamButton.disabled = true;
  } catch (error) {
    if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
      alert('Camera/microphone access was denied. Please allow access to use this feature.');
    } else if (error.name === 'NotFoundError' || error.name === 'DevicesNotFoundError') {
      alert('No camera or microphone found. Please connect a camera/microphone and try again.');
    } else {
      alert('Failed to start webcam. Please ensure camera/microphone permissions are granted and devices are available.');
    }
  }
};

answerButton.onclick = async () => {
  if (!pc) {
    alert("Please start your webcam first!");
    return;
  }
  const callId = callInput.value;
  if (!callId) {
    alert("Please enter a Call ID to answer.");
    return;
  }

  const callDoc = firestore.collection('calls').doc(callId);
  const answerCandidates = callDoc.collection('answerCandidates');
  const offerCandidates = callDoc.collection('offerCandidates');

  pc.onicecandidate = (event) => {
    event.candidate && answerCandidates.add(event.candidate.toJSON());
  };

  const callData = (await callDoc.get()).data();
  if (!callData || !callData.offer) {
    alert("No call found with that ID or offer not present.");
    return;
  }

  const offerDescription = callData.offer;
  await pc.setRemoteDescription(new RTCSessionDescription(offerDescription));

  const answerDescription = await pc.createAnswer();
  await pc.setLocalDescription(answerDescription);

  const answer = {
    type: answerDescription.type,
    sdp: answerDescription.sdp,
  };

  await callDoc.update({ answer });

  offerCandidates.onSnapshot((snapshot) => {
    snapshot.docChanges().forEach((change) => {
      if (change.type === 'added') {
        let data = change.doc.data();
        pc.addIceCandidate(new RTCIceCandidate(data));
      }
    });
  });

  hangupButton.disabled = false;
  answerButton.disabled = true;
};

hangupButton.onclick = () => {
  resetCall();
};

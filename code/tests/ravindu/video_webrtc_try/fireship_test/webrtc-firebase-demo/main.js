// import './style.css';

// import firebase from 'firebase/app';
// import 'firebase/firestore';

// const firebaseConfig = {
//   apiKey: "AIzaSyBubdSfljjucCKUUwEwh15EtZFLywbsGEQ",
//   authDomain: "test-webrtc-f155e.firebaseapp.com",
//   projectId: "test-webrtc-f155e",
//   storageBucket: "test-webrtc-f155e.firebasestorage.app",
//   messagingSenderId: "674163171327",
//   appId: "1:674163171327:web:c8f988f1605a01bd9291ca",
//   measurementId: "G-VV8L1PP7GZ"
// };

// if (!firebase.apps.length) {
//   firebase.initializeApp(firebaseConfig);
// }
// const firestore = firebase.firestore();

// const servers = {
//   iceServers: [
//     {
//       urls: ['stun:stun1.l.google.com:19302', 'stun:stun2.l.google.com:19302'],
//     },
//   ],
//   iceCandidatePoolSize: 10,
// };

// // Global State
// let pc = null; // Initialize pc here, will be created on webcam start
// let localStream = null;
// let remoteStream = null;

// // HTML elements
// const webcamButton = document.getElementById('webcamButton');
// const webcamVideo = document.getElementById('webcamVideo');
// const callButton = document.getElementById('callButton');
// const callInput = document.getElementById('callInput');
// const answerButton = document.getElementById('answerButton');
// const remoteVideo = document.getElementById('remoteVideo');
// const hangupButton = document.getElementById('hangupButton');

// // Helper function to reset UI and connection
// const resetCall = () => {
//   if (localStream) {
//     localStream.getTracks().forEach(track => track.stop());
//     localStream = null;
//   }
//   if (remoteStream) {
//     remoteStream.getTracks().forEach(track => track.stop());
//     remoteStream = null;
//   }
//   if (pc) {
//     pc.close();
//     pc = null;
//   }

//   webcamVideo.srcObject = null;
//   remoteVideo.srcObject = null;
//   callInput.value = '';

//   webcamButton.disabled = false;
//   callButton.disabled = true;
//   answerButton.disabled = true;
//   hangupButton.disabled = true;
// };

// // 1. Setup media sources
// webcamButton.onclick = async () => {
//   // Prompt user to allow camera/microphone access
//   alert('This site needs access to your camera and microphone. Please click "Allow" in your browser prompt.');
//   try {
//     localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
//     webcamVideo.srcObject = localStream;

//     // Initialize RTCPeerConnection here, after user media is obtained
//     pc = new RTCPeerConnection(servers);

//     // Push tracks from local stream to peer connection
//     localStream.getTracks().forEach((track) => {
//       pc.addTrack(track, localStream);
//     });

//     // Pull tracks from remote stream, add to video stream
//     // IMPORTANT: Assign remote stream to video element when tracks arrive
//     pc.ontrack = (event) => {
//       console.log('ontrack event received:', event.streams);
//       // event.streams[0] will be the MediaStream object from the remote peer
//       if (remoteVideo.srcObject !== event.streams[0]) {
//         remoteVideo.srcObject = event.streams[0];
//         remoteStream = event.streams[0]; // Keep a reference to the remote stream
//       }
//     };

//     // Optional: Log ICE connection state for debugging
//     pc.oniceconnectionstatechange = () => {
//       console.log(`ICE connection state: ${pc.iceConnectionState}`);
//       if (pc.iceConnectionState === 'disconnected' || pc.iceConnectionState === 'failed') {
//         console.log('Call disconnected or failed.');
//         // Consider calling hangup() here if you want automatic hangup on disconnection
//       }
//     };

//     pc.onconnectionstatechange = () => {
//       console.log(`Peer connection state: ${pc.connectionState}`);
//     };


//     callButton.disabled = false;
//     answerButton.disabled = false;
//     webcamButton.disabled = true;

//   } catch (error) {
//     if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
//       alert('Camera/microphone access was denied. Please allow access to use this feature.');
//     } else if (error.name === 'NotFoundError' || error.name === 'DevicesNotFoundError') {
//       alert('No camera or microphone found. Please connect a camera/microphone and try again.');
//     } else {
//       alert('Failed to start webcam. Please ensure camera/microphone permissions are granted and devices are available.');
//     }
//   }
// };

// // 2. Create an offer
// callButton.onclick = async () => {
//   if (!pc) {
//     alert("Please start your webcam first!");
//     return;
//   }

//   // Reference Firestore collections for signaling
//   const callDoc = firestore.collection('calls').doc();
//   const offerCandidates = callDoc.collection('offerCandidates');
//   const answerCandidates = callDoc.collection('answerCandidates');

//   callInput.value = callDoc.id;

//   // Get candidates for caller, save to db
//   pc.onicecandidate = (event) => {
//     event.candidate && offerCandidates.add(event.candidate.toJSON());
//   };

//   // Create offer
//   const offerDescription = await pc.createOffer();
//   await pc.setLocalDescription(offerDescription);

//   const offer = {
//     sdp: offerDescription.sdp,
//     type: offerDescription.type,
//   };

//   await callDoc.set({ offer });

//   // Listen for remote answer
//   callDoc.onSnapshot((snapshot) => {
//     const data = snapshot.data();
//     if (data?.answer && !pc.currentRemoteDescription) { // Ensure answer exists and remote description not already set
//       console.log('Received answer:', data.answer);
//       const answerDescription = new RTCSessionDescription(data.answer);
//       pc.setRemoteDescription(answerDescription);
//     }
//   });

//   // When answered, add candidate to peer connection
//   answerCandidates.onSnapshot((snapshot) => {
//     snapshot.docChanges().forEach((change) => {
//       if (change.type === 'added') {
//         const candidate = new RTCIceCandidate(change.doc.data());
//         console.log('Adding answer candidate:', candidate);
//         pc.addIceCandidate(candidate);
//       }
//     });
//   });

//   hangupButton.disabled = false;
//   callButton.disabled = true; // Disable call button once call is initiated
// };

// // 3. Answer the call with the unique ID
// answerButton.onclick = async () => {
//   if (!pc) {
//     alert("Please start your webcam first!");
//     return;
//   }

//   const callId = callInput.value;
//   if (!callId) {
//     alert("Please enter a Call ID to answer.");
//     return;
//   }

//   const callDoc = firestore.collection('calls').doc(callId);
//   const answerCandidates = callDoc.collection('answerCandidates');
//   const offerCandidates = callDoc.collection('offerCandidates');

//   pc.onicecandidate = (event) => {
//     event.candidate && answerCandidates.add(event.candidate.toJSON());
//   };

//   const callData = (await callDoc.get()).data();
//   if (!callData || !callData.offer) {
//     alert("No call found with that ID or offer not present.");
//     return;
//   }

//   const offerDescription = callData.offer;
//   await pc.setRemoteDescription(new RTCSessionDescription(offerDescription));

//   const answerDescription = await pc.createAnswer();
//   await pc.setLocalDescription(answerDescription);

//   const answer = {
//     type: answerDescription.type,
//     sdp: answerDescription.sdp,
//   };

//   await callDoc.update({ answer });

//   offerCandidates.onSnapshot((snapshot) => {
//     snapshot.docChanges().forEach((change) => {
//       console.log('Offer candidate change:', change);
//       if (change.type === 'added') {
//         let data = change.doc.data();
//         pc.addIceCandidate(new RTCIceCandidate(data));
//       }
//     });
//   });

//   hangupButton.disabled = false;
//   answerButton.disabled = true; // Disable answer button once answered
// };

// // 4. Hangup
// hangupButton.onclick = async () => {
//   console.log('Hanging up call...');
//   resetCall();

//   // Optional: Delete the call document from Firestore after hanging up
//   // const callId = callInput.value;
//   // if (callId) {
//   //   try {
//   //     await firestore.collection('calls').doc(callId).delete();
//   //     console.log('Call document deleted from Firestore.');
//   //   } catch (error) {
//   //     console.error('Error deleting call document:', error);
//   //   }
//   // }
// };
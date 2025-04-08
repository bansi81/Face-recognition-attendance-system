/**
 * Webcam.js - Basic webcam handling for face registration and attendance
 */

class Webcam {
    constructor(webcamElement, facingMode = 'user', canvasElement = null) {
        this._webcamElement = webcamElement;
        this._facingMode = facingMode;
        this._webcamList = [];
        this._streamList = [];
        this._selectedDeviceId = '';
        this._canvasElement = canvasElement;
    }

    get facingMode() {
        return this._facingMode;
    }

    set facingMode(value) {
        this._facingMode = value;
    }

    get webcamList() {
        return this._webcamList;
    }

    get webcamCount() {
        return this._webcamList.length;
    }

    get selectedDeviceId() {
        return this._selectedDeviceId;
    }

    /* Get all video input devices info */
    async getVideoInputs() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) {
            console.error("enumerateDevices() not supported.");
            return [];
        }

        const devices = await navigator.mediaDevices.enumerateDevices();
        const videoDevices = devices.filter(device => device.kind === 'videoinput');
        return videoDevices;
    }

    /* Start the webcam stream */
    async start(startStream = true) {
        this._webcamElement.style.transform = "";
        
        return new Promise((resolve, reject) => {
            this.stop();
            
            /* Get video input devices info */
            this.getVideoInputs().then(videoInputs => {
                this._webcamList = videoInputs;
                
                if (startStream) {
                    /* Start video stream */
                    this.startStream().then(() => {
                        resolve(this._facingMode);
                    }).catch(error => {
                        reject(error);
                    });
                } else {
                    resolve(this._selectedDeviceId);
                }
            }).catch(error => {
                reject(error);
            });
        });
    }

    /* Start the video stream */
    async startStream() {
        this.stop();

        const constraints = {
            audio: false,
            video: {
                facingMode: this._facingMode
            }
        };

        if (this._selectedDeviceId) {
            constraints.video.deviceId = { exact: this._selectedDeviceId };
        }

        return new Promise((resolve, reject) => {
            navigator.mediaDevices.getUserMedia(constraints).then(stream => {
                this._streamList.push(stream);
                this._webcamElement.srcObject = stream;
                
                this._webcamElement.play();
                resolve(this._facingMode);
            }).catch(error => {
                console.error("Error starting video stream:", error);
                reject(error);
            });
        });
    }

    /* Stop the webcam stream */
    stop() {
        this._streamList.forEach(stream => {
            stream.getTracks().forEach(track => {
                track.stop();
            });
        });
        this._streamList = [];
    }

    /* Take a screenshot */
    snap() {
        if (this._canvasElement === null) {
            this._canvasElement = document.createElement('canvas');
        }

        const videoWidth = this._webcamElement.videoWidth;
        const videoHeight = this._webcamElement.videoHeight;

        if (videoWidth && videoHeight) {
            // Set canvas size to match video
            this._canvasElement.width = videoWidth;
            this._canvasElement.height = videoHeight;

            // Draw the video frame to canvas
            const context = this._canvasElement.getContext('2d');
            context.drawImage(this._webcamElement, 0, 0, videoWidth, videoHeight);

            // Get base64 encoded image data
            const dataUrl = this._canvasElement.toDataURL('image/jpeg');
            return dataUrl;
        }
        
        return null;
    }
}

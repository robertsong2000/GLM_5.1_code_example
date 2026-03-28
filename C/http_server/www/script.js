function fetchTime() {
    fetch('/api/time')
        .then(r => r.json())
        .then(data => {
            document.getElementById('time').textContent = 'Server time: ' + data.time;
        })
        .catch(err => {
            document.getElementById('time').textContent = 'Error: ' + err;
        });
}

function sendEcho() {
    fetch('/api/echo', {
        method: 'POST',
        body: 'Hello from browser at ' + new Date().toISOString()
    })
        .then(r => r.text())
        .then(data => {
            document.getElementById('echo-result').textContent = 'Echo: ' + data;
        })
        .catch(err => {
            document.getElementById('echo-result').textContent = 'Error: ' + err;
        });
}

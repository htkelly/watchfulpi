//Send a request to the hub API to get a JSON object with all sensors, iterate through the sensors and for each one, populate a div element with the sensor information and controls, and append it to the dashboard page
function getSensors() {
    let xhr = new XMLHttpRequest();
    xhr.open("GET", "/api/sensor/all", false);
    xhr.send();
    var jsonObject = JSON.parse(xhr.responseText);
    var sensors = jsonObject.sensors
    var outerdiv = document.getElementById('outer');
    for (var sensor of Object.keys(sensors))
    {   
        if (sensors[sensor]["mode"] == 0) {var status_ = 'Standby'}
        else if (sensors[sensor]["mode"] == 1) {var status_ = 'Sensing'}
        else if (sensors[sensor]["mode"] == 2) {var status_ = 'Streaming'}
        else {let status = 'Not available'}
        var innerdiv = document.createElement("div")
        innerdiv.className = "ui stacked segment"
        innerdiv.innerHTML = 
        '<h1>' + sensor + '</h1><p>IP: ' + sensors[sensor]["ip"] + '<br>Status: ' + status_ +
        '</p><a href="/' + sensor + '/eventsview" class="ui icon button"><i class ="icon folder"></i></a>' +
        '<a href="/' + sensor + '/streamview" class="ui icon button"><i class ="icon camera"></i></a>' +
        '<button class="ui right floated button" onclick=standby("' + sensor + '")>Standby</button>' +
        '<button class="ui right floated button" onclick=sense("' + sensor + '")>Sense</button>' +
        '<button class="ui right floated button" onclick=stream("' + sensor + '")>Stream</button>'
        outerdiv.appendChild(innerdiv)
    }
}

//Send a request to the hub API to put a single sensor in standby mode
function standby(sensor) {
    let xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/sensor/" + sensor + "?mode=0", false);
    xhr.send();
    console.log(xhr.responseText);
    location.reload();
}

//Send a request to the hub API to put a single sensor in sense mode
function sense(sensor) {
    let xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/sensor/" + sensor + "?mode=1", false);
    xhr.send();
    console.log(xhr.responseText);
    location.reload();
}

//Send a request to the hub API to put a single sensor in streaming mode
function stream(sensor) {
    let xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/sensor/" + sensor + "?mode=2", false);
    xhr.send();
    console.log(xhr.responseText);
    location.reload();
}

//Send a request to the hub API to put a all sensors in standby mode
function allStandby() {
    let xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/sensor/all?mode=0", false);
    xhr.send();
    console.log(xhr.responseText);
    location.reload();
}

//Send a request to the hub API to put a all sensors in sense mode
function allSense() {
    let xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/sensor/all?mode=1", false);
    xhr.send();
    console.log(xhr.responseText);
    location.reload();
}

//Send a request to the hub API to put a all sensors in streaming mode
function allStream() {
    let xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/sensor/all?mode=2", false);
    xhr.send();
    console.log(xhr.responseText);
    location.reload();
}
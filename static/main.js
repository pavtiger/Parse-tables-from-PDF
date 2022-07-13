let socket = io("http://" + window.location.hostname + ":" + window.location.port);


socket.on("progress", function(message) {
    console.log(message);

    let timer = document.getElementById("timer");
    timer.innerHTML = "Time elapsed: " + Math.round(message["time"] / 1000) + " seconds";

    let terminal = document.getElementById("console");
    terminal.innerHTML = message["stdout"];
});


socket.on("download", function(paths) {
    paths.forEach(function (path, index) {
        let a = document.createElement("a");
        a.href = path;
        a.download = path.split("/").pop();
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    });
});


form.addEventListener("submit", (e) => {
    e.preventDefault();

    let dict = {}
    const formData = new FormData(document.querySelector("form"))
    for (let pair of formData.entries()) {
        dict[pair[0]] = pair[1];
    }
    socket.emit("send", dict)
});

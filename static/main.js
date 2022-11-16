let socket = io("http://" + window.location.hostname + ":" + window.location.port);
let terminal_text = [], start_time, processing_in_progress = false;


socket.on("progress", function(message) {
    let terminal = document.getElementById("console");
    terminal_text.push(message["stdout"])
    terminal.innerHTML = terminal_text.join("");

    processing_in_progress = true;
});


socket.on("delete_row", function() {
    terminal_text.pop();
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

    processing_in_progress = false;
});


form.addEventListener("submit", (e) => {
    e.preventDefault();
    start_time = Date.now();

    let dict = {}
    const formData = new FormData(document.querySelector("form"))
    for (let pair of formData.entries()) {
        dict[pair[0]] = pair[1];
    }
    socket.emit("send", dict)
});


setInterval(function() {
    if (processing_in_progress) {
        let timer = document.getElementById("timer");
        timer.innerHTML = "Time elapsed: " + Math.round((Date.now() - start_time) / 1000) + " seconds";
    }
}, 1000);

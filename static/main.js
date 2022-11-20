const socket = io("http://" + window.location.hostname + ":" + window.location.port);
let terminal_text = [], start_time, processing_in_progress = false;
let form = document.forms.submit_link;


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
    let stop_button = document.getElementById("stop_button");
    stop_button.style.color = "black";

    paths.forEach(function (path) {
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
    let console = document.getElementById("console");

    let dict = {}
    const formData = new FormData(document.querySelector("form"));
    for (let pair of formData.entries()) {
        if (pair[0] === "link" && pair[1] === "") {
            console.innerHTML = "The link you entered is incorrect. Check if it begins with http:// or https://";
            return;
        }
        dict[pair[0]] = pair[1];
    }

    // Clear console
    console.innerHTML = "";
    terminal_text = [];

    let stop_button = document.getElementById("stop_button");
    stop_button.style.color = "red";

    socket.emit("send", dict)
});


form.addEventListener("reset", (e) => {
    e.preventDefault();

    let stop_button = document.getElementById("stop_button");
    stop_button.style.color = "black";
    socket.emit("stop");
});


setInterval(function() {
    if (processing_in_progress) {
        let timer = document.getElementById("timer");
        timer.innerHTML = "Time elapsed: " + Math.round((Date.now() - start_time) / 1000) + " seconds";
    }
}, 200);

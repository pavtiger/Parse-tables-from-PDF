const socket = io("http://" + window.location.hostname + ":" + window.location.port);
let start_time, processing_in_progress = false;
let form = document.forms.submit_link;


socket.on("progress", function(message) {
    let border = document.getElementById(message["index"]).querySelector(".slider_border");
    let progress_bar = border.querySelector(".slider");

    if (progress_bar === null) {  // Create slider div element
        progress_bar = document.createElement("div");
        progress_bar.style.width = "0%";
        progress_bar.classList.add('slider');
        border.append(progress_bar)
    }

    progress_bar.style.width = message["stdout"].toString() + "%";
    processing_in_progress = true;
});

socket.on("init_info", function(message) {
    let text_field = document.getElementById("init_info");
    text_field.innerHTML += message["stdout"] + "\n";
    processing_in_progress = true;
});

socket.on("processing_finished", function(message) {
    let div = document.getElementById(message["index"])
    let progress_bar = div.querySelector(".slider");
    progress_bar.style.width = "100%";

    let button = div.querySelector(".button-placeholder");
    button.innerHTML = "<div class=\"glow-on-hover centered\"><div class=\"button_text\">Download results</div></div>";
    button.style.visibility = "visible";

    let target_dropdown = div.querySelector(".download_div");
    target_dropdown.append(button)
});

socket.on("nothing_found_on_page", function(message) {
    let div = document.getElementById(message["index"])

    let button = div.querySelector(".button-placeholder");
    button.innerHTML = "<div class=\"not-glow-on-hover centered\"><div class=\"nothing_found_text\">No tables found</div></div>";
    button.style.visibility = "visible";

    let slider_border = div.querySelector(".slider_border");
    let empty_bar = document.createElement("div");
    empty_bar.style.width = "100%";
    empty_bar.classList.add('empty-slider');

    slider_border.append(empty_bar)

    let target_dropdown = div.querySelector(".download_div");
    target_dropdown.append(button)
});

socket.on("init", function(message) {
    let console_div = document.getElementById("console");
    for (let table_ind = 0; table_ind < message["page_cnt"]; ++table_ind) {
        const img = new Image();  // Create image from data received from server
        let image_data = message["image_data"];

        let base64String = btoa(
            new Uint8Array(image_data[table_ind])
                .reduce((data, byte) => data + String.fromCharCode(byte), "")
        );

        img.src = 'data:image/jpg;base64,' + base64String;
        img.width = 500;

        let header = htmlToElements('<div class="row header align-items-center border" style="height: 10%">\n' +
            '                <div class="col-lg-1 col-md-1 col-sm-1 col-1"><div class="p-0 page_index">' + (table_ind + 1).toString() + '</div></div>\n' +
            '                <div class="col-lg-7 col-md-7 col-sm-5 col-5 align-items-center"><div class="p-3 slider_border" style="background: #111; background-clip: content-box; border-radius: 5px">\n' +
            '                </div></div>\n' +
            '                <div class="col-lg-3 col-md-3 col-sm-4 col-4"><div class="p-2 download_div">' +
            '                    <div class="button-placeholder centered"><div class="button_text">Download</div></div>' +
            '                </div></div>\n' +
            '                <div class="col-lg-1 col-md-1 col-sm-2 col-2">\n' +
            '                    <div class="p-1 expand_elem"><input class="dropdown" type="image" src="expand.png" style="max-width: 30%" alt="Input"> </div>\n' +
            '                </div>\n' +
            '            </div>\n' +
            '\n' +
            '            <div class="row main_body justify-content-start align-items-center">\n' +
            '                <div class="col-lg-5 image">\n' +
            '                    <div class="image_div"></div>\n' +
            '                </div>\n' +
            // '                <div class="col-lg-5 image">\n' +
            // '                    <div class="p-3 border bg-light">Output</div>\n' +
            // '                </div>\n' +
            '            </div>');

        let div = document.createElement("div");
        div.id = table_ind.toString();
        div.style.height = "40%"

        for (let i = 0; i < header.length; i++) {
            div.appendChild(header[i])
        }

        console_div.append(div);

        let target_dropdown = div.querySelector(".main_body");
        target_dropdown.style.display = "none";

        let image_div = div.querySelector(".image_div");
        image_div.append(img)
    }
});


document.body.onclick = function(e) {  // All mouse clicks event
    e=window.event? event.srcElement: e.target;
    let className = e.className;

    if (className.includes('dropdown') || className.includes('expand_elem')) {
        // Click is in dropdown div
        let up = 3;
        if (e.className === "dropdown") {
            up = 4;
        }
        for (let i = 0; i < up; ++i) {
            e = e.parentElement;
        }
        let target_dropdown = e.querySelector(".main_body");
        if (target_dropdown.style.display === "none") {
            target_dropdown.style.display = "inline";
        } else {
            target_dropdown.style.display = "none";
        }
    }

    if (className.includes('button_text') || className.includes('glow-on-hover')) {
        let up = 5;
        if (e.className === "button_text") {
            up = 6;
        }
        for (let i = 0; i < up; ++i) {
            e = e.parentElement;
        }

        socket.emit("download_task", e.id)
    }
}


socket.on("work_finish", function(message) {  // Receive and download results
    if (message["download"]) {
        let paths = message["paths"]
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
    }
    processing_in_progress = false;
});


form.addEventListener("submit", (e) => {  // Submit button press event
    e.preventDefault();
    start_time = Date.now();
    let console_element = document.getElementById("init_info");

    if (processing_in_progress) {
        console_element.innerHTML += "You already have an ongoing request. Cancel your current run first\n";
        return;
    }

    let dict = {}
    const formData = new FormData(document.querySelector("form"));
    for (let pair of formData.entries()) {
        if (pair[0] === "link" && pair[1] === "") {
            console_element.innerHTML = "The link you entered is incorrect. Check if it begins with http:// or https://";
            return;
        }
        dict[pair[0]] = pair[1];
    }
    dict["download_results"] = document.getElementById("download_checkbox").checked;

    // Clear console
    console_element.innerHTML = "";

    // Clear text field
    let init_info = document.getElementById("init_info");
    init_info.innerHTML = "";

    // Clear console div element
    let console = document.getElementById("console");
    console.innerHTML = "";

    let stop_button = document.getElementById("stop_button");
    stop_button.style.color = "red";

    socket.emit("send", dict)
});


form.addEventListener("reset", (e) => {  // Stop button press event
    e.preventDefault();

    let stop_button = document.getElementById("stop_button");
    stop_button.style.color = "black";
    processing_in_progress = false;

    socket.emit("stop");
});


/**
 * @param {String} HTML representing any number of sibling elements
 * @return {NodeList}
 */
function htmlToElements(html) {
    let template = document.createElement('template');
    template.innerHTML = html;
    return template.content.childNodes;
}


setInterval(function() {  // Setup timer update every 200ms
    if (processing_in_progress) {
        let timer = document.getElementById("timer");
        timer.innerHTML = "Time elapsed: " + Math.round((Date.now() - start_time) / 1000) + " seconds";
    }
}, 200);

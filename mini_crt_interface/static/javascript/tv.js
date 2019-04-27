function getActivePlayer() {
    return new Promise((resolve, reject) => {
        $.ajax({
            url: '/api/tv',
            type: 'GET',
            contentType: 'application/json',
            data: {},
            success: (response) => {
                if (!response) {
                    reject('No active media on TV');
                } else if (!response.hasOwnProperty('error')) {
                    resolve(response);
                } else {
                    console.log(`Error: ${JSON.stringify(response)}`);
                }
            },
            error: (err) => {
                console.log(`Error: ${JSON.stringify(err)}`);
            }
        });
    });
}

function updateGUI(activeContent) {

    $('.artwork').attr('src', activeContent['artwork']);
    $('.title.title__primary').text(activeContent['title']);
    if (activeContent['show']) {
        $('.title.title__secondary').text(`${activeContent['show']} - S${activeContent['season']}E${activeContent['episode']}`);
    }

    const glitchImages = $('.artwork.glitch');
    const paused = $('.paused-container');

    switch (activeContent['state']) {
        case 'playing':
            glitchImages.css('display', 'initial');
            paused.css('display', 'none');
            allowScroll = true;
            break;
        case 'paused':
            glitchImages.css('display', 'none');
            paused.css('display', 'flex');
            allowScroll = false;
            break;
        default:
            break;
    }
}
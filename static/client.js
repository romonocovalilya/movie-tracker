let db = {};
let franchiseTitles = {};
let watchedIds = [];
let likes = [];
let dislikes = [];
let currentFranchise = 'empty';
let searchQuery = '';

async function loadData() {
    const res = await fetch('/api/data');
    const data = await res.json();
    db = data.db;
    franchiseTitles = data.titles;
    watchedIds = data.watched;
    likes = data.likes;
    dislikes = data.dislikes;

    const keys = Object.keys(db);
    if (currentFranchise === 'empty' && keys.length > 0) {
        currentFranchise = keys[0];
    } else if (keys.length === 0) {
        currentFranchise = 'empty';
    }
    renderTabs();
    renderList();
}

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('search-input').addEventListener('input', (e) => {
        searchQuery = e.target.value.toLowerCase().trim();
        renderList();
    });
    loadData();
});

function toggleForm(formId) {
    document.getElementById(formId).classList.toggle('hidden');
}

function renderTabs() {
    const tabsContainer = document.getElementById('tabs-container');
    tabsContainer.innerHTML = '';
    const keys = Object.keys(db);

    if (keys.length === 0) {
        tabsContainer.innerHTML = '<span style="color: #777; padding: 10px 0;">Хронологий нет. Создайте первую! 👇</span>';
    } else {
        keys.forEach(key => {
            const btn = document.createElement('button');
            btn.className = `tab-btn ${currentFranchise == key ? 'active' : ''}`;
            btn.innerText = franchiseTitles[key];
            btn.onclick = () => switchChronology(key);
            tabsContainer.appendChild(btn);
        });
    }
    const libBtn = document.createElement('button');
    libBtn.className = `tab-btn library-btn ${currentFranchise === 'library' ? 'active' : ''}`;
    libBtn.innerText = '📚 Моя Библиотека';
    libBtn.onclick = () => switchChronology('library');
    tabsContainer.appendChild(libBtn);
}

async function addNewFranchise(event) {
    event.preventDefault();
    const name = document.getElementById('franchise-name').value.trim();
    await fetch('/api/franchise', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ name })
    });
    document.getElementById('franchise-form').reset();
    toggleForm('add-franchise-container');
    currentFranchise = 'empty'; 
    await loadData();
}

async function addNewMedia(event) {
    event.preventDefault();
    if (currentFranchise === 'library' || currentFranchise === 'empty') return alert('Выберите хронологию!');
    
    const title = document.getElementById('form-title').value;
    const type = document.getElementById('form-type').value;
    const year = document.getElementById('form-year').value;
    const timeline = document.getElementById('form-timeline').value;
    const video = document.getElementById('form-video').value;

    await fetch('/api/media', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ title, type, year, timeline, video, franchise_id: currentFranchise })
    });
    document.getElementById('media-form').reset();
    toggleForm('add-media-container');
    await loadData();
}

async function sendRate(id, type) {
    await fetch('/api/rate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ id, type })
    });
    await loadData();
}

function renderList() {
    const listContainer = document.getElementById('chronology-list');
    const noResultsMessage = document.getElementById('no-results');
    const libraryOverview = document.getElementById('library-overview');
    
    listContainer.innerHTML = '';
    libraryOverview.innerHTML = '';
    noResultsMessage.classList.add('hidden');

    if (currentFranchise === 'empty') {
        listContainer.innerHTML = '<div style="text-align:center; color:#555; margin-top:40px;">Создайте свою первую киновселенную через синюю кнопку.</div>';
        return;
    }

    if (currentFranchise === 'library') {
        libraryOverview.classList.remove('hidden');
        let libraryHtml = '<h2>📊 Статус ваших хронологий</h2>';
        let allWatchedMedia = [];

        Object.keys(db).forEach(key => {
            const total = db[key].length;
            const watchedCount = db[key].filter(item => watchedIds.includes(item.id)).length;
            const percent = total > 0 ? Math.round((watchedCount / total) * 100) : 0;
            const isCompleted = percent === 100 && total > 0;

            libraryHtml += `
                <div class="franchise-progress-card ${isCompleted ? 'completed' : ''}">
                    <div class="progress-header"><span>${franchiseTitles[key]}</span><span>${watchedCount}/${total} (${percent}%)</span></div>
                    <div class="progress-bar-bg"><div class="progress-bar-fill" style="width: ${percent}%"></div></div>
                </div>
            `;
            db[key].forEach(item => { if (watchedIds.includes(item.id)) allWatchedMedia.push(item); });
        });

        libraryOverview.innerHTML = libraryHtml;
        const filteredLibrary = allWatchedMedia.filter(item => item.title.toLowerCase().includes(searchQuery));
        if (filteredLibrary.length === 0) noResultsMessage.classList.remove('hidden');
        else buildCategoryBlock("Просмотренный контент", filteredLibrary, listContainer);
    } else {
        libraryOverview.classList.add('hidden');
        const filteredData = db[currentFranchise].filter(item => item.title.toLowerCase().includes(searchQuery));
        if (filteredData.length === 0) {
            if(db[currentFranchise].length === 0) listContainer.innerHTML = '<div style="text-align:center; color:#555; margin-top:40px;">Эта хронология пуста.</div>';
            else noResultsMessage.classList.remove('hidden');
            return;
        }
        const movies = filteredData.filter(item => item.type === 'movie');
        const series = filteredData.filter(item => item.type === 'series');
        const cartoons = filteredData.filter(item => item.type === 'cartoon');
        const animatedSeries = filteredData.filter(item => item.type === 'animated_series');

        if (movies.length > 0) buildCategoryBlock("🎬 Фильмы", movies, listContainer);
        if (series.length > 0) buildCategoryBlock("📺 Сериалы", series, listContainer);
        if (cartoons.length > 0) buildCategoryBlock("🧸 Мультфильмы", cartoons, listContainer);
        if (animatedSeries.length > 0) buildCategoryBlock("🧬 Мультсериалы", animatedSeries, listContainer);
    }
}

function buildCategoryBlock(categoryName, itemsArray, container) {
    const section = document.createElement('div');
    section.className = 'category-section';
    const title = document.createElement('h2');
    title.className = 'category-title';
    title.innerText = categoryName;
    section.appendChild(title);

    itemsArray.forEach(item => {
        const isWatched = watchedIds.includes(item.id);
        const isLiked = likes.includes(item.id);
        const isDisliked = dislikes.includes(item.id);

        const card = document.createElement('div');
        card.className = `movie-card ${isWatched ? 'watched' : ''}`;
        let typeText = item.type === 'movie' ? 'Фильм' : item.type === 'series' ? 'Сериал' : item.type === 'cartoon' ? 'Мультфильм' : 'Мультсериал';

        card.innerHTML = `
            <div class="movie-info">
                <span class="badge ${item.type}">${typeText}</span>
                <h3>${item.title}</h3>
                <p>Год: ${item.year} | Хронология: <strong>${item.timeline}</strong></p>
            </div>
            <div class="card-buttons">
                <div class="rating-buttons">
                    <button class="like-btn ${isLiked ? 'active' : ''}" onclick="sendRate(${item.id}, 'like')">👍</button>
                    <button class="dislike-btn ${isDisliked ? 'active' : ''}" onclick="sendRate(${item.id}, 'dislike')">👎</button>
                </div>
                <!-- ПРЯМАЯ ССЫЛКА ВМЕСТО ПЛЕЕРА -->
                <a href="${item.video}" target="_blank" rel="noopener noreferrer" class="play-btn" style="text-decoration: none; display: inline-block; text-align: center;">
                    ▶ Открыть сайт
                </a>
                <button class="watch-btn" onclick="sendRate(${item.id}, 'watch')">${isWatched ? '✓ Просмотрено' : 'Буду смотреть'}</button>
            </div>
        `;
        section.appendChild(card);
    });
    container.appendChild(section);
}

function switchChronology(franchiseKey) {
    currentFranchise = franchiseKey;
    searchQuery = '';
    document.getElementById('search-input').value = '';
    renderTabs();
    renderList();
}

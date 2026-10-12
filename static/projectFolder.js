(() => {
    // Directory handles are granted by the user, never inferred from uploaded filenames.
    const locations = new WeakMap();
    const workspaces = new Map();
    let database = null, saveQueue = Promise.resolve(), selectionVersion = 0, picking = false, bookmarkTime = 0;
    async function open() {
        if (!window.showDirectoryPicker) throw new Error('Saving beside images requires Chrome or Edge. Open this app there and choose Open folder.');
        selectionVersion++;
        picking = true;
        try { return await readDirectory(await window.showDirectoryPicker({ mode: 'readwrite' })); }
        finally { picking = false; }
    }
    async function readDirectory(root) {
        const files = [];
        async function visit(directory, prefix) {
            const entries = [];
            for await (const entry of directory.values()) entries.push(entry);
            const stems = new Map();
            for (const entry of entries) {
                if (entry.kind !== 'file' || !window.SAM2FileUtils.isSupportedImageFile(entry)) continue;
                const stem = entry.name.replace(/\.[^.]+$/, '').toLowerCase();
                stems.set(stem, (stems.get(stem) || 0) + 1);
            }
            for (const entry of entries) {
                if (entry.kind === 'directory') { await visit(entry, `${prefix}${entry.name}/`); continue; }
                if (!window.SAM2FileUtils.isSupportedImageFile(entry) && !/\.(json|csv|txt|xml)$/i.test(entry.name)) continue;
                const file = await entry.getFile();
                Object.defineProperty(file, 'webkitRelativePath', { value: `${prefix}${file.name}` });
                locations.set(file, { root, path: `${prefix}${file.name}`.slice(root.name.length + 1), directory,
                    revisions: new Map(), ambiguous: stems.get(file.name.replace(/\.[^.]+$/, '').toLowerCase()) > 1 });
                files.push(file);
            }
        }
        await visit(root, `${root.name}/`);
        return files;
    }
    function workspaceDatabase() {
        if (!database) database = new Promise((resolve, reject) => {
            if (!window.indexedDB) { reject(new Error('Browser storage unavailable')); return; }
            const request = window.indexedDB.open('microscopyStudioWorkspaces', 1);
            request.onupgradeneeded = () => request.result.createObjectStore('projects');
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
            request.onblocked = () => reject(new Error('Browser storage is blocked'));
        });
        return database;
    }
    async function storedWorkspace(projectId, value) {
        const db = await workspaceDatabase();
        return new Promise((resolve, reject) => {
            const transaction = db.transaction('projects', value ? 'readwrite' : 'readonly');
            const store = transaction.objectStore('projects');
            const request = value ? store.put(value, projectId) : store.get(projectId);
            transaction.oncomplete = () => resolve(value || request.result || null);
            transaction.onabort = transaction.onerror = () => reject(transaction.error || request.error);
        });
    }
    function imagePath(file) { return locations.get(file)?.path || file.webkitRelativePath?.split('/').slice(1).join('/') || file.name; }
    async function remember(projectId, files, currentFile, { identity = null, filter = 'all' } = {}) {
        const target = locations.get(currentFile);
        if (!projectId || !target || files.some(file => locations.get(file)?.root !== target.root)) return false;
        bookmarkTime = Math.max(Date.now(), bookmarkTime + 1);
        const value = { handle: target.root, folderName: target.root.name, paths: files.map(imagePath),
            bookmarkId: crypto.randomUUID(), updatedAt: bookmarkTime,
            lastPath: imagePath(currentFile), identity, filter };
        workspaces.set(projectId, value);
        // Keep the bookmark usable for manual reconnection if handle storage is unavailable.
        try { window.localStorage.setItem(`microscopyStudioWorkspace:${projectId}`, JSON.stringify({ ...value, handle: undefined })); }
        catch { /* Private profiles can disable storage. Folder autosave still works. */ }
        const write = saveQueue.then(() => storedWorkspace(projectId, value));
        saveQueue = write.catch(() => {});
        try { await write; return true; } catch { return false; }
    }
    async function restore(projectId, requestAccess = false) {
        if (!projectId || picking) return { status: 'none' };
        const version = selectionVersion;
        let value = workspaces.get(projectId);
        if (!value) {
            try { value = await storedWorkspace(projectId); } catch { /* Fall back to a reconnectable bookmark. */ }
            try {
                const latest = JSON.parse(window.localStorage.getItem(`microscopyStudioWorkspace:${projectId}`));
                // An interrupted/failed handle write must not reopen an older folder.
                if (latest && (!value || latest.bookmarkId !== value.bookmarkId && latest.updatedAt >= value.updatedAt)) value = latest;
            } catch { /* Nothing to restore when storage is disabled. */ }
            if (version !== selectionVersion || picking) return { status: 'cancelled' };
            value = workspaces.get(projectId) || value;
            if (value) workspaces.set(projectId, value);
        }
        if (!value) return { status: 'none' };
        if (version !== selectionVersion || picking) return { status: 'cancelled' };
        if (!value.handle) return { ...value, status: 'missing' };
        try {
            let permission = await value.handle.queryPermission({ mode: 'readwrite' });
            if (permission !== 'granted' && requestAccess) permission = await value.handle.requestPermission({ mode: 'readwrite' });
            if (permission !== 'granted') return { ...value, status: 'permission' };
            const files = (await readDirectory(value.handle)).filter(file => !window.SAM2FileUtils.isSupportedImageFile(file) || value.paths.includes(imagePath(file)));
            if (version !== selectionVersion || picking) return { status: 'cancelled' };
            return { ...value, files, status: files.some(window.SAM2FileUtils.isSupportedImageFile) ? 'ready' : 'missing' };
        } catch (error) { return { ...value, status: 'missing', error: error.message }; }
    }
    async function attach(files) {
        const candidates = await open();
        const digest = async file => Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', await file.arrayBuffer()))).join(',');
        const matches = [];
        for (const file of files) {
            const hash = await digest(file);
            const matching = [];
            for (const candidate of candidates.filter(item => item.name === file.name && item.size === file.size)) {
                if (await digest(candidate) === hash) matching.push(candidate);
            }
            if (matching.length !== 1) throw new Error(`Choose the folder containing exactly one copy of ${file.name}. No images were opened.`);
            matches.push([file, matching[0]]);
        }
        for (const [file, candidate] of matches) locations.set(file, locations.get(candidate));
    }
    function location(file) {
        const result = locations.get(file);
        if (!result) throw new Error('Choose Open folder to grant saving access to the project image folder. Your edits remain unsaved.');
        if (result.ambiguous) throw new Error('Two images in this folder share the same stem. Use distinct names before saving annotations.');
        return result;
    }
    async function current(directory, name) {
        try { return await (await (await directory.getFileHandle(name)).getFile()).text(); }
        catch (error) { if (error.name === 'NotFoundError') return null; throw error; }
    }
    async function read(file, name) {
        const target = location(file);
        const content = await current(target.directory, name);
        target.revisions.set(name, content);
        return content;
    }
    async function writeUnlocked(file, name, content) {
        const target = location(file);
        if (!name || /[\\/]/.test(name)) throw new Error('Invalid annotation filename.');
        if (await target.directory.queryPermission({ mode: 'readwrite' }) !== 'granted') throw new Error('Folder write permission expired. Reopen the project folder before saving.');
        const before = await current(target.directory, name);
        if (!target.revisions.has(name)) {
            if (before !== null) throw new Error('An annotation already exists. Reopen the image to load it before saving.');
            target.revisions.set(name, null);
        }
        if (before !== target.revisions.get(name)) throw new Error('Annotation changed outside the app. Reopen the folder before saving; your edits remain unsaved.');
        const handle = await target.directory.getFileHandle(name, { create: true });
        let stream;
        try { stream = await handle.createWritable(); await stream.write(content); await stream.close(); }
        catch (error) {
            if (stream) await stream.abort().catch(() => {});
            // A newly created empty file belongs to this failed attempt; allow Retry save.
            if (before === null && await current(target.directory, name) === '') target.revisions.set(name, '');
            throw error;
        }
        target.revisions.set(name, content);
    }
    async function write(file, name, content) {
        if (window.navigator?.locks) return window.navigator.locks.request(
            `microscopy-annotation:${file.webkitRelativePath || file.name}:${name}`,
            () => writeUnlocked(file, name, content));
        return writeUnlocked(file, name, content);
    }
    // Queue inspection must not change the revision baseline used by active edits.
    const peek = (file, name) => current(location(file).directory, name);
    window.SAM2ProjectFolder = { open, attach, read, peek, write, remember, restore, imagePath, has: file => locations.has(file) };
})();

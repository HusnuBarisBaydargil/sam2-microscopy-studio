(() => {
    function matchFolderFiles(files) {
        const { isSupportedImageFile, imageSortName, stripExtension } = window.SAM2FileUtils;
        const images = files.filter(isSupportedImageFile).sort((a, b) => imageSortName(a).localeCompare(imageSortName(b), undefined, { numeric: true }));
        const key = file => stripExtension(imageSortName(file)).toLowerCase();
        const imageCounts = new Map(), jsonFiles = new Map();
        for (const image of images) imageCounts.set(key(image), (imageCounts.get(key(image)) || 0) + 1);
        for (const file of files.filter(file => /\.json$/i.test(file.name))) {
            const matches = jsonFiles.get(key(file)) || [];
            matches.push(file); jsonFiles.set(key(file), matches);
        }
        const annotations = new Map();
        for (const image of images) {
            const matches = jsonFiles.get(key(image)) || [];
            if (matches.length) annotations.set(image, imageCounts.get(key(image)) === 1 && matches.length === 1 ? matches[0] : null);
        }
        return { images, annotations };
    }

    // The live editor accessors preserve read/write timing while saves are pending.
    function createSaveChanges(editor, { request, render, message }) {
        return async function saveChanges() {
            if (!editor.state.dirty) { editor.saveError = false; return; }
            editor.saving = true;
            render();
            try {
                if (window.SAM2ProjectFolder) {
                    if (editor.folderLoadFailed) throw new Error("Existing annotations could not be loaded. Import a valid annotation before saving.");
                    const file = editor.queue[editor.currentIndex];
                    const result = await request('api/project/segmentation', { action: 'export_labelme',
                        image: editor.state.document.image, document: editor.state.document, image_name: file.name });
                    result.labelme.imagePath = file.name;
                    await window.SAM2ProjectFolder.write(file, file.name.replace(/\.[^.]+$/, '') + '.json', JSON.stringify(result.labelme, null, 2));
                    editor.state.markSaved(editor.state.document); editor.saveError = false;
                    return;
                }
                const result = await request('api/project/segmentation', {
                    action: 'save', image: editor.state.document.image, document: editor.state.document, revision: editor.revision,
                    image_name: editor.queue[editor.currentIndex].name || 'image.png'
                });
                editor.state.markSaved(result.document);
                editor.revision = result.revision;
                editor.saveError = false;
                message('All completed objects saved automatically.');
            } catch (error) {
                editor.saveError = true;
                throw new Error(`Save failed. Your edits are still here. ${error.message}`);
            } finally { editor.saving = false; }
        };
    }
    window.SAM2PolygonPersistence = { matchFolderFiles, createSaveChanges };
})();

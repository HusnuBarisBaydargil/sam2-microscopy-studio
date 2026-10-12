(() => {
    function correctedBoundary(points, start, end, replacement, otherSide = false) {
        function arc(from, to) {
            const begin = from.edge + from.t;
            const end = to.edge + to.t;
            const finish = end > begin ? end : end + points.length;
            const result = [from.point];
            for (let vertex = Math.floor(begin) + 1; vertex < finish; vertex++) result.push(points[vertex % points.length]);
            result.push(to.point);
            return result;
        }
        const forward = arc(start, end), backward = arc(end, start);
        const length = path => path.slice(1).reduce((sum, point, index) => sum + Math.hypot(point[0] - path[index][0], point[1] - path[index][1]), 0);
        const replaceForward = (length(forward) <= length(backward)) !== otherSide;
        const path = [start.point, ...replacement, end.point];
        return { points: replaceForward ? [...path, ...backward.slice(1, -1)] : [...forward, ...replacement.slice().reverse()],
            removed: replaceForward ? forward : backward.slice().reverse(), retained: replaceForward ? backward : forward, path };
    }

    function geometryContains(geometry, point) {
        const [x, y] = point, points = geometry.points;
        if (geometry.type === 'rectangle') return x >= Math.min(points[0][0], points[1][0]) && x <= Math.max(points[0][0], points[1][0]) && y >= Math.min(points[0][1], points[1][1]) && y <= Math.max(points[0][1], points[1][1]);
        if (geometry.type === 'circle') return Math.hypot(x - points[0][0], y - points[0][1]) <= Math.hypot(points[1][0] - points[0][0], points[1][1] - points[0][1]);
        let inside = false;
        for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
            const a = points[i], b = points[j];
            if ((a[1] > y) !== (b[1] > y) && x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]) inside = !inside;
        }
        return inside;
    }

    function duplicatePoints(points) {
        return points.map((point, index) => points.some((other, i) => i !== index && point[0] === other[0] && point[1] === other[1]) ? index : -1).filter(index => index >= 0);
    }
    window.SAM2PolygonGeometry = { correctedBoundary, geometryContains, duplicatePoints };
})();

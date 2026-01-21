def snapshot_dom(page):
    return page.evaluate("""
    () => {
        return Array.from(document.querySelectorAll('*')).map(el => {
            const rect = el.getBoundingClientRect();
            const style = window.getComputedStyle(el);

            return {
                tag: el.tagName,
                x: rect.x,
                y: rect.y,
                w: rect.width,
                h: rect.height,
                position: style.position,
                opacity: style.opacity,
                transform: style.transform
            };
        });
    }
    """)

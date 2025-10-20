// Tab functionality
async function fillSlider() {
    const response = await fetch('/schedule.json');
    let data = await response.json();

    const days = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'];

    days.forEach(day => {
        var panel = document.getElementById(`${day}-panel`);
        var panelList = document.createElement('div');
        panelList.classList.add('list')
        data[day].forEach((prog) => {
            panelList.innerHTML+= `\n<div class="day_${day}"><div class="show-slot" data-img="${prog.image}" data-src="${prog.source}"><div class="time">${prog.time}:00&nbsp;<small>NPT</small></div><div class="divider"></div><p class="title">${prog.program}</p></div>\n`;
        });
        panel.appendChild(panelList);
    });
}

document.addEventListener("DOMContentLoaded", function() {
    // Reorder tabs and update dates based on today
    reorderAndUpdateSchedule();
    
    fillSlider().then(() => {
        // Initialize schedule functionality if element exists
        if (document.querySelector('.schedule-mini')) {
            initScheduleMini();
        }
    });

    // Tab click tracking
    document.querySelectorAll('[role="tab"]').forEach(function(tab) {
        tab.addEventListener("click", function(event) {
            var target = event.target.matches('[role="tab"]') ? event.target : event.target.closest('[role="tab"]');
            var dateElement = target.querySelector(".date-full");
            var dateText = dateElement ? dateElement.innerText : "";

            if (event.isTrusted && window.dataLayer) {
                window.dataLayer.push({
                    event: "carousel",
                    carousel_interaction: "Tab View",
                    tile_text: dateText
                });
            }
        }, true);
    });

    // Initialize schedule functionality if element exists
    // if (document.querySelector('.schedule-mini')) {
    //    initScheduleMini();
    // }
});

function reorderAndUpdateSchedule() {
    const daysOfWeek = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
    const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const today = new Date();
    const currentDay = daysOfWeek[today.getDay()];
    
    // Find all tab containers
    const tablist = document.querySelector('[role="tablist"]');
    if (!tablist) return;
    
    const tabs = Array.from(tablist.querySelectorAll('[role="tab"]'));
    const scheduleSection = document.querySelector('.schedule');
    const panels = scheduleSection ? Array.from(scheduleSection.querySelectorAll('[role="tabpanel"]')) : [];
    
    // Find today's index
    let todayIndex = tabs.findIndex(tab => tab.classList.contains(`day_${currentDay}`));
    if (todayIndex === -1) todayIndex = 0;
    
    // Reorder tabs
    const reorderedTabs = [...tabs.slice(todayIndex), ...tabs.slice(0, todayIndex)];
    const reorderedPanels = [...panels.slice(todayIndex), ...panels.slice(0, todayIndex)];
    
    // Clear and re-append tabs
    tablist.innerHTML = '';
    reorderedTabs.forEach(tab => tablist.appendChild(tab));
    
    // Clear and re-append panels
    if (scheduleSection) {
        scheduleSection.innerHTML = '';
        reorderedPanels.forEach(panel => scheduleSection.appendChild(panel));
    }
    
    // Update dates for all tabs
    reorderedTabs.forEach((tab, index) => {
        const date = new Date(today);
        date.setDate(today.getDate() + index);
        
        const dayName = daysOfWeek[date.getDay()];
        const dayShort = dayName.substring(0, 3);
        const month = monthNames[date.getMonth()];
        const day = date.getDate();
        const year = date.getFullYear();
        
        // Update day name
        const dayFullSpan = tab.querySelector('.day .date-full');
        const dayShortSpan = tab.querySelector('.day .date-short');
        if (dayFullSpan) dayFullSpan.textContent = dayName;
        if (dayShortSpan) dayShortSpan.textContent = dayShort;
        
        // Update date
        const dateFullSpan = tab.querySelector('.date .date-full');
        const dateShortSpan = tab.querySelector('.date .date-short');
        if (dateFullSpan) dateFullSpan.textContent = `${month} ${day}, ${year}`;
        if (dateShortSpan) dateShortSpan.textContent = `${day}/${String(year).slice(-2)}`;
    });
}
const program = document.getElementById('program');
const title = document.getElementById('title');
const srcrl = document.getElementById('source-url');
const thumb = document.getElementById('pragram-img');

function highlightCurrentShow() {
    const now = new Date();
    const currentHour = now.getHours();
    const currentMinute = now.getMinutes();
    const currentTimeInMinutes = currentHour * 60 + currentMinute;
    
    // Get the active panel
    const activePanel = document.querySelector('[role="tabpanel"]:not([hidden])');
    if (!activePanel) return;
    
    const tabDateText = document.querySelector('[role="tab"][aria-selected="true"]').querySelector('.date .date-full');
    const tabDate = new Date(tabDateText.textContent);
    
    const isToday = tabDate.getDate() === now.getDate() &&
                    tabDate.getMonth() === now.getMonth() &&
                    tabDate.getFullYear() === now.getFullYear();


    const showSlots = activePanel.querySelectorAll('.show-slot');
    let currentShow = null;
    let currentShowElement = null;
    
    showSlots.forEach((slot, index) => {
        const timeText = slot.querySelector('.time').textContent.trim();
        const timeMatch = timeText.match(/(\d{1,2}):(\d{2})/);
        
        if (timeMatch) {
            const showHour = parseInt(timeMatch[1]);
            const showMinute = parseInt(timeMatch[2]);
            const showTimeInMinutes = showHour * 60 + showMinute;
            
            // Check if this show is currently airing
            const nextSlot = showSlots[index + 1];
            let nextShowTime = 24 * 60; // End of day
            
            if (nextSlot) {
                const nextTimeText = nextSlot.querySelector('.time').textContent.trim();
                const nextTimeMatch = nextTimeText.match(/(\d{1,2}):(\d{2})/);
                if (nextTimeMatch) {
                    nextShowTime = parseInt(nextTimeMatch[1]) * 60 + parseInt(nextTimeMatch[2]);
                }
            }
            
            if (currentTimeInMinutes >= showTimeInMinutes && currentTimeInMinutes < nextShowTime) {
                currentShow = slot;
                currentShowElement = slot.closest('.day_Sunday, .day_Monday, .day_Tuesday, .day_Wednesday, .day_Thursday, .day_Friday, .day_Saturday');
            }
        }
        
        // Remove previous highlights
        slot.querySelector('.divider').style.background="";
        slot.querySelector('.time small').classList.remove('live-tag');
        slot.classList.remove('current-show');
        // const parent = slot.closest('.day_Sunday, .day_Monday, .day_Tuesday, .day_Wednesday, .day_Thursday, .day_Friday, .day_Saturday');
        // if (parent) parent.classList.remove('current-show');
    });
    // Highlight current show
    if (currentShow && isToday) {
        // Remove previous highlights
        // activePanel.querySelectorAll('.current-show').forEach((e)=>{e.querySelector('.divider').style.background="";e.querySelector('.time small').classList.remove('live-tag');e.classList.remove('current-show')})

        srcrl.setAttribute('data-url', currentShow.getAttribute('data-src'));

        imgrl = currentShow.getAttribute('data-img');
        if (imgrl.trim().length != 0) {
            thumb.src=imgrl;
        } else {
            thumb.src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='50' height='50' viewBox='0 0 24 24'%3E%3Cpath fill='%23ffffff' d='M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 14.5v-9l6 4.5-6 4.5z'/%3E%3C/svg%3E";
        }
        program.innerHTML=currentShow.querySelector('.title').innerHTML;


        currentShow.classList.add('current-show');
        if (currentShowElement) {
            currentShowElement.classList.add('current-show');
        }
        
        // Change divider color and add live tag
        const divider = currentShow.querySelector('.divider');
        if (divider) {
            divider.style.background = '#ffea00';
        }
        
        const timeSmall = currentShow.querySelector('.time small');
        if (timeSmall) {
            timeSmall.classList.add('live-tag');
        }
            setTimeout(function() {
                highlightCurrentShow();
            }, 20000);

    }
    
    return currentShowElement;
}

function initScheduleMini() {
    const $ = jQuery;

    // Tab system
    function TabSystem(container) {
        this.container = container;
        this.keys = {end: 35, home: 36, left: 37, up: 38, right: 39, down: 40};
        this.direction = {37: -1, 38: -1, 39: 1, 40: 1};

        this.init = function() {
            this.tablist = this.container.querySelectorAll('[role="tablist"]')[0];
            this.tabs = this.container.querySelectorAll('[role="tab"]');
            this.panels = this.container.querySelectorAll('[role="tabpanel"]');

            for (var i = 0; i < this.tabs.length; i++) {
                this.addListeners(i);
            }
        };

        this.addListeners = function(index) {
            var tab = this.tabs[index];
            tab.addEventListener("click", this.clickEventListener.bind(this));
            tab.addEventListener("keydown", this.keydownEventListener.bind(this));
            tab.index = index;
        };

        this.activateTab = function(tab, focus) {
            this.deactivateTabs();
            tab.removeAttribute("tabindex");
            tab.setAttribute("aria-selected", "true");

            var panel = document.getElementById(tab.getAttribute("aria-controls"));
            panel.removeAttribute("hidden");
            panel.setAttribute("tabindex", "0");

            if (focus) tab.focus();
            
            // Highlight current show when tab changes
            setTimeout(function() {
                highlightCurrentShow();
            }, 100);
        };

        this.deactivateTabs = function() {
            for (var i = 0; i < this.tabs.length; i++) {
                this.tabs[i].setAttribute("tabindex", "-1");
                this.tabs[i].setAttribute("aria-selected", "false");
            }
            for (var i = 0; i < this.panels.length; i++) {
                this.panels[i].setAttribute("hidden", "hidden");
            }
        };

        this.clickEventListener = function(event) {
            this.activateTab(event.currentTarget, false);
        };

        this.keydownEventListener = function(event) {
            switch(event.keyCode) {
                case this.keys.end:
                    event.preventDefault();
                    this.activateTab(this.tabs[this.tabs.length - 1], true);
                    break;
                case this.keys.home:
                    event.preventDefault();
                    this.activateTab(this.tabs[0], true);
                    break;
                case this.keys.left:
                case this.keys.right:
                    this.determineOrientation(event);
                    break;
            }
        };

        this.determineOrientation = function(event) {
            var key = event.keyCode;
            if (key === this.keys.left || key === this.keys.right) {
                var tab = event.currentTarget;
                if (this.tabs[tab.index + this.direction[key]]) {
                    this.tabs[tab.index + this.direction[key]].focus();
                } else if (key === this.keys.left) {
                    this.tabs[this.tabs.length - 1].focus();
                } else if (key === this.keys.right) {
                    this.tabs[0].focus();
                }
            }
        };
    }

    // Initialize the schedule
    var content = $("section.content");
    var prevButton = $(".schedule-mini .fa-chevron-left");
    var nextButton = $(".schedule-mini .fa-chevron-right");

    // Initialize slick slider for main content
    content.slick({
        accessibility: false,
        dots: false,
        infinite: false,
        swipe: false,
        arrows: false,
        slidesToShow: 1,
        slidesToScroll: 1
    });

    // Initialize tabs for each slide
    content.find(".slick-slide").each(function() {
        new TabSystem(this).init();
    });

    // Function to initialize tab content slider
    function initializeTabContent($tab) {
        var panelId = $tab.attr("aria-controls");
        var $panel = $("#" + panelId);

        if ($panel.length) {
            $panel.attr("tabindex", 0);
            var $list = $panel.find(".list");

            // Initialize slick for the content if not already done
            if (!$tab.data("isSlickLoaded")) {
                $list.slick({
                    initialSlide: 0,
                    dots: false,
                    infinite: false,
                    prevArrow: prevButton,
                    nextArrow: nextButton,
                    slidesToShow: 5,
                    slidesToScroll: 5,
                    responsive: [
                        {
                            breakpoint: 1200,
                            settings: {slidesToShow: 4, slidesToScroll: 4}
                        },
                        {
                            breakpoint: 995,
                            settings: {slidesToShow: 3, slidesToScroll: 3}
                        },
                        {
                            breakpoint: 700,
                            settings: {slidesToShow: 2, slidesToScroll: 2}
                        },
                        {
                            breakpoint: 500,
                            settings: {slidesToShow: 1, slidesToScroll: 1}
                        }
                    ]
                }).on("swipe", function(event) {
                    event.stopPropagation();
                    if (window.dataLayer) {
                        window.dataLayer.push({
                            event: "carousel",
                            carousel_interaction: "Tile Drag"
                        });
                    }
                });

                $tab.data("isSlickLoaded", true);
                
                // After slick is initialized, scroll to current time
                setTimeout(function() {
                    scrollToCurrentTime($list);
                }, 200);
            } else {
                $list.slick("slickSetOption", "prevArrow", prevButton, true);
                $list.slick("slickSetOption", "nextArrow", nextButton, true);
            }
        }
    }

    // Function to scroll to current time
    function scrollToCurrentTime($list) {
        const currentShow = highlightCurrentShow();
        
        if (currentShow && $list.hasClass('slick-initialized')) {
            const $currentShow = $(currentShow);
            const slideIndex = $currentShow.index();
            
            if (slideIndex >= 0) {
                $list.slick('slickGoTo', slideIndex);
            }
        }
    }

    // Activate first tab by default AND initialize its content
    setTimeout(function() {
        var firstTab = content.find('[role="tab"]').first();
        if (firstTab.length) {
            // Activate the tab
            firstTab.click();

            // Initialize the tab's content slider
            initializeTabContent(firstTab);
        }
    }, 100);

    // Navigation button handlers
    prevButton.on("click", function() {
        content.slick("slickPrev");
        if (window.dataLayer) {
            window.dataLayer.push({
                event: "carousel",
                carousel_interaction: "Arrow Left"
            });
        }
    });

    nextButton.on("click", function() {
        content.slick("slickNext");
        if (window.dataLayer) {
            window.dataLayer.push({
                event: "carousel",
                carousel_interaction: "Arrow Right"
            });
        }
    });

    // Tab activation handler
    content.find('[role="tab"]').on("click", function() {
        var $this = $(this);
        initializeTabContent($this);
    });

    // Keyboard navigation for panels
    content.find('[role="tabpanel"]').on("keydown", function(event) {
        switch(event.which) {
            case 37: // left arrow
                prevButton.click();
                break;
            case 39: // right arrow
                nextButton.click();
                break;
        }
    });
}

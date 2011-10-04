$(function() {
    $("#cb_show_closed").click(
        function() {
            $("tr.closed").toggle(this.checked)
        })
})
